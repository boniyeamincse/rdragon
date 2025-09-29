"""
Nuclei Vulnerability Scanning Module for ReconDragon

Runs nuclei vulnerability scans with JSON output.
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

from base import BaseModule

logger = logging.getLogger(__name__)


class NucleiModule(BaseModule):
    """
    Nuclei vulnerability scanning module for ReconDragon.

    Runs nuclei templates against targets with configurable severity and tags.
    """

    def __init__(self):
        self.timeout = 1800  # 30 minutes timeout
        self.templates_dir = "/opt/nuclei-templates"  # Default nuclei templates location

    @property
    def name(self) -> str:
        return "nuclei"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _parse_nuclei_output(self, json_file: Path) -> List[Dict[str, Any]]:
        """Parse nuclei JSON output."""
        if not json_file.exists():
            return []

        try:
            results = []
            with open(json_file, 'r') as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
            return results
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to parse nuclei output: {e}")
            return []

    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute nuclei vulnerability scanning.

        Args:
            target: Target URL or IP
            outdir: Output directory
            execute: Whether to actually run the scan
            **kwargs: Additional options (severity, tags, templates, etc.)

        Returns:
            Dict with standardized module results
        """
        start_time = time.time()

        # Configuration from kwargs
        severity = kwargs.get('severity', 'info,low,medium,high,critical')
        tags = kwargs.get('tags', 'misc,generic')
        templates = kwargs.get('templates', self.templates_dir)

        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        json_file = output_dir / "nuclei_results.json"

        # Build nuclei command
        cmd = [
            "nuclei",
            "-u", target,
            "-json",
            "-o", str(json_file),
            "-severity", severity,
            "-tags", tags,
            "-t", templates,
            "-timeout", "10",  # Request timeout
            "-rate-limit", "150"  # Requests per second
        ]

        # Add additional options
        if kwargs.get('no-interactsh', True):
            cmd.append("-no-interactsh")

        success = False
        error_msg = None
        raw_output = None

        if execute:
            try:
                logger.info(f"Running nuclei scan on {target}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=True
                )
                success = True
                raw_output = result.stdout
                logger.info("Nuclei scan completed successfully")
            except subprocess.TimeoutExpired:
                error_msg = "Nuclei scan timed out"
                logger.error(error_msg)
            except subprocess.CalledProcessError as e:
                error_msg = f"Nuclei failed: {e.stderr}"
                logger.error(error_msg)
            except FileNotFoundError:
                error_msg = "nuclei binary not found. Please install nuclei."
                logger.error(error_msg)
        else:
            # Dry-run
            logger.info(f"Dry-run: Would execute {' '.join(cmd)}")
            success = True

        # Parse results
        vulnerabilities = self._parse_nuclei_output(json_file)

        end_time = time.time()

        # Categorize by severity
        severity_counts = {}
        for vuln in vulnerabilities:
            sev = vuln.get('info', {}).get('severity', 'unknown')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        summary = {
            "target": target,
            "vulnerabilities_found": len(vulnerabilities),
            "severity_breakdown": severity_counts,
            "templates_used": templates,
            "scan_duration": round(end_time - start_time, 2)
        }

        if error_msg:
            summary["error"] = error_msg

        artifacts = []
        if json_file.exists():
            artifacts.append(str(json_file))

        return {
            "module": self.name,
            "version": self.version,
            "target": target,
            "start_time": start_time,
            "end_time": end_time,
            "success": success,
            "summary": summary,
            "artifacts": artifacts,
            "raw": raw_output
        }