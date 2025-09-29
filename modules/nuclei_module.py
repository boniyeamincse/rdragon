"""
Nuclei Vulnerability Scanning Module for ReconDragon

Integrates Nuclei templated scans with JSON output and fallback capabilities.
"""

import json
import logging
import os
import subprocess
import time
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Union, Optional
from shutil import which

from base import BaseModule

logger = logging.getLogger(__name__)


class NucleiModule(BaseModule):
    """
    Nuclei vulnerability scanning module with templated scans and fallback.

    Provides comprehensive vulnerability detection using Nuclei templates,
    with safe fallback for offline environments.
    """

    def __init__(self):
        self.timeout: int = int(os.getenv("NUCLEI_TIMEOUT", "1800"))  # 30 minutes default
        self.templates_index_path: str = os.getenv("NUCLEI_TEMPLATES_INDEX", "templates_index.json")
        self.workspace_authorized: bool = os.getenv("WORKSPACE_AUTHORIZED", "false").lower() == "true"

    @property
    def name(self) -> str:
        return "nuclei"

    @property
    def version(self) -> str:
        return "2.0.0"

    def _check_tool_availability(self) -> bool:
        """Check if nuclei is available."""
        return which("nuclei") is not None

    def _generate_job_id(self, targets: List[str]) -> str:
        """Generate a job ID based on targets."""
        target_str = "|".join(sorted(targets))
        return hashlib.md5(target_str.encode()).hexdigest()[:8]

    def _build_nuclei_commands(self, targets: List[str], outdir: str, templates_path: Optional[str],
                              severity: str, threads: int) -> List[List[str]]:
        """Build nuclei command(s) for execution."""
        commands = []

        # Prepare target input
        if len(targets) == 1:
            target_arg = ["-u", targets[0]]
        else:
            # Write targets to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write('\n'.join(targets))
                target_file = f.name
            target_arg = ["-l", target_file]

        base_cmd = ["nuclei", "-oJ", "-severity", severity, "-c", str(threads)]

        if templates_path:
            base_cmd.extend(["-t", templates_path])

        base_cmd.extend(target_arg)

        # Split into multiple commands if needed (for now, single command)
        commands.append(base_cmd)

        return commands

    def _run_nuclei(self, commands: List[List[str]], outdir: str, job_id: str) -> bool:
        """Execute nuclei commands."""
        output_file = Path(outdir) / f"nuclei_{job_id}.json"

        # For simplicity, run the first command and append to output
        cmd = commands[0] + ["-o", str(output_file)]

        try:
            logger.info(f"Running nuclei command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )
            if result.returncode == 0:
                logger.info("Nuclei scan completed successfully")
                return True
            else:
                logger.error(f"Nuclei failed with return code {result.returncode}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("Nuclei scan timed out")
            return False
        except Exception as e:
            logger.error(f"Error running nuclei: {e}")
            return False

    def _parse_nuclei_output(self, output_file: Path) -> List[Dict[str, Any]]:
        """Parse nuclei JSON output."""
        if not output_file.exists():
            return []

        findings = []
        try:
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        findings.append(json.loads(line))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to parse nuclei output: {e}")

        return findings

    def _prioritize_findings(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group findings by severity and provide samples."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        grouped = {"critical": [], "high": [], "medium": [], "low": [], "info": []}

        for finding in findings:
            sev = finding.get("info", {}).get("severity", "info").lower()
            if sev in grouped:
                grouped[sev].append(finding)

        prioritized = {}
        for sev in ["critical", "high", "medium", "low", "info"]:
            if grouped[sev]:
                prioritized[sev] = {
                    "count": len(grouped[sev]),
                    "sample_findings": grouped[sev][:5]  # First 5 as samples
                }

        return prioritized

    def _fallback_scan(self, targets: List[str], outdir: str, templates_path: Optional[str],
                      severity: str) -> Dict[str, Any]:
        """Conservative fallback using keyword matching against templates index."""
        logger.info("Nuclei not available, using fallback keyword matching")

        # Load templates index
        index_path = Path(templates_path or self.templates_index_path)
        if not index_path.exists():
            logger.warning(f"Templates index not found: {index_path}")
            return {"fallback_findings": [], "note": "Templates index not available"}

        try:
            with open(index_path, 'r') as f:
                templates = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load templates index: {e}")
            return {"fallback_findings": [], "note": "Failed to load templates index"}

        findings = []
        severity_list = severity.split(',')

        # Very conservative: check if target URLs contain keywords from templates
        # This is a placeholder for actual HTTP header/banner checking
        for target in targets:
            for template in templates.get("templates", []):
                if template.get("info", {}).get("severity", "").lower() in severity_list:
                    # Simple string match (very conservative)
                    keywords = template.get("keywords", [])
                    if any(keyword.lower() in target.lower() for keyword in keywords):
                        findings.append({
                            "template": template.get("id", "unknown"),
                            "info": template.get("info", {}),
                            "matched_url": target,
                            "fallback": True
                        })

        return {
            "fallback_findings": findings,
            "note": "Conservative keyword matching against target URLs. Real banner/header checking not implemented."
        }

    def run(self, target: Union[str, List[str]], outdir: str, execute: bool = False,
            templates_path: Optional[str] = None, severity: str = "low,medium,high,critical",
            threads: int = 10) -> Dict[str, Any]:
        """
        Execute nuclei vulnerability scanning.

        Args:
            target: Target URL(s) or IP(s) (str or list)
            outdir: Output directory for results
            execute: Whether to actually run nuclei
            templates_path: Path to nuclei templates
            severity: Comma-separated severity levels
            threads: Number of concurrent threads

        Returns:
            Dict with scan results and findings
        """
        targets = [target] if isinstance(target, str) else target
        if not targets:
            raise ValueError("No targets provided")

        job_id = self._generate_job_id(targets)
        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        commands = self._build_nuclei_commands(targets, str(output_dir), templates_path, severity, threads)

        if not execute:
            return {
                "module": self.name,
                "version": self.version,
                "status": "dry-run",
                "job_id": job_id,
                "commands": commands,
                "targets": targets,
                "templates_path": templates_path,
                "severity": severity,
                "threads": threads,
                "raw": {
                    "note": "TODO: Respect workspace.authorized gating for aggressive templates"
                }
            }

        # Execute mode
        success = False
        findings = []

        if self._check_tool_availability():
            success = self._run_nuclei(commands, str(output_dir), job_id)
            if success:
                output_file = output_dir / f"nuclei_{job_id}.json"
                findings = self._parse_nuclei_output(output_file)
        else:
            fallback_result = self._fallback_scan(targets, str(output_dir), templates_path, severity)
            findings = fallback_result.get("fallback_findings", [])

        prioritized_findings = self._prioritize_findings(findings)

        # Count total by severity
        counts = {}
        for sev, data in prioritized_findings.items():
            counts[sev] = data["count"]

        result = {
            "module": self.name,
            "version": self.version,
            "status": "completed" if success else "fallback" if findings else "failed",
            "job_id": job_id,
            "targets": targets,
            "findings": prioritized_findings,
            "counts": counts,
            "total_findings": sum(counts.values()),
            "artifacts": [str(output_dir / f"nuclei_{job_id}.json")] if success else [],
            "raw": {
                "commands": commands,
                "templates_path": templates_path,
                "severity": severity,
                "threads": threads,
                "note": "TODO: Respect workspace.authorized gating for aggressive templates"
            }
        }

        if not success and not findings:
            result["error"] = "Nuclei not available and fallback found no matches"

        return result