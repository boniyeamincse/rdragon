"""
Subdomains Enumeration Module for ReconDragon

This module integrates multiple subdomain enumeration tools: Subfinder, Amass, and Findomain.
It provides unified execution with automatic tool detection, fallback, and result merging.

Features:
- Multi-tool integration (Subfinder, Amass, Findomain)
- Automatic tool availability detection
- Dry-run mode for planning
- Secure subprocess execution without shell injection
- Retry logic for transient failures
- Unified output merging
- Configurable timeouts
"""

import os
import subprocess
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from shutil import which
from base import BaseModule

logger = logging.getLogger(__name__)


class SubdomainsModule(BaseModule):
    """
    Multi-tool subdomain enumeration module.

    Integrates Subfinder, Amass, and Findomain for comprehensive subdomain discovery.
    """

    def __init__(self):
        self.max_retries = 2
        self.default_tools = ["subfinder", "amass", "findomain"]

    @property
    def name(self) -> str:
        return "subdomains"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _sanitize_target(self, target: str) -> str:
        """Sanitize target domain for safe use."""
        # Basic domain validation and sanitization
        target = target.strip().lower()
        if not target or '.' not in target or not target.replace('.', '').isalnum():
            raise ValueError(f"Invalid target domain: {target}")
        return target

    def _get_available_tools(self, tools: List[str]) -> List[str]:
        """Check which tools are available on the system."""
        available = []
        for tool in tools:
            if which(tool):
                available.append(tool)
        return available

    def _build_command(self, tool: str, target: str, output_file: str, timeout: int) -> List[str]:
        """Build command for the given tool."""
        if tool == "subfinder":
            return ["subfinder", "-d", target, "-o", output_file, "-timeout", str(timeout), "-silent"]
        elif tool == "amass":
            # TODO: Enable passive sources in amass config for better results
            return ["amass", "enum", "-d", target, "-o", output_file, "-timeout", str(timeout)]
        elif tool == "findomain":
            return ["findomain", "-t", target, "-o", output_file, "--quiet"]
        else:
            raise ValueError(f"Unknown tool: {tool}")

    def _run_command_with_retry(self, cmd: List[str], output_file: str, timeout: int) -> bool:
        """Run command with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Running command (attempt {attempt + 1}): {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 30,  # Extra time for processing
                    check=True
                )
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return True
                else:
                    logger.warning(f"Command succeeded but no valid output: {output_file}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout on attempt {attempt + 1}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Command failed on attempt {attempt + 1}: {e.stderr}")
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")

            if attempt < self.max_retries:
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
        return False

    def _merge_subdomains(self, output_files: List[str], merged_file: str):
        """Merge unique subdomains from multiple tool outputs."""
        unique_subdomains = set()
        for outfile in output_files:
            if os.path.exists(outfile):
                with open(outfile, 'r') as f:
                    for line in f:
                        subdomain = line.strip()
                        if subdomain and '.' in subdomain:
                            unique_subdomains.add(subdomain.lower())

        with open(merged_file, 'w') as f:
            for subdomain in sorted(unique_subdomains):
                f.write(f"{subdomain}\n")

    def run(self, target: str, outdir: str, execute: bool = False, tools: List[str] = None, timeout: int = 300) -> Dict[str, Any]:
        """
        Execute subdomain enumeration using multiple tools.

        Args:
            target: Target domain
            outdir: Output directory
            execute: Whether to actually run commands (default: False for dry-run)
            tools: List of tools to use (default: ["subfinder", "amass", "findomain"])
            timeout: Timeout per tool in seconds

        Returns:
            Plugin contract JSON dict
        """
        start_time = time.time()
        tools = tools or self.default_tools

        try:
            target = self._sanitize_target(target)
            outdir_path = Path(outdir)
            outdir_path.mkdir(parents=True, exist_ok=True)

            available_tools = self._get_available_tools(tools) if execute else tools

            commands = []
            output_files = []
            raw_outputs = {}

            for tool in available_tools:
                outfile = outdir_path / f"{tool}_output.txt"
                output_files.append(str(outfile))
                cmd = self._build_command(tool, target, str(outfile), timeout)
                commands.append({"tool": tool, "command": cmd, "output_file": str(outfile)})

                if execute:
                    success = self._run_command_with_retry(cmd, str(outfile), timeout)
                    raw_outputs[tool] = "success" if success else "failed"
                else:
                    raw_outputs[tool] = "dry-run"

            merged_file = outdir_path / "subdomains.txt"

            if execute:
                self._merge_subdomains(output_files, str(merged_file))
                total_subdomains = sum(1 for _ in open(merged_file)) if merged_file.exists() else 0
            else:
                total_subdomains = None  # Not computed in dry-run

            end_time = time.time()

            return {
                "module": self.name,
                "version": self.version,
                "target": target,
                "start_time": start_time,
                "end_time": end_time,
                "success": True,
                "summary": {"total_subdomains": total_subdomains},
                "artifacts": [str(merged_file)] + output_files,
                "raw": {
                    "commands": commands,
                    "available_tools": available_tools,
                    "tool_outputs": raw_outputs
                }
            }

        except Exception as e:
            logger.error(f"Error in subdomains module: {e}")
            end_time = time.time()
            return {
                "module": self.name,
                "version": self.version,
                "target": target,
                "start_time": start_time,
                "end_time": end_time,
                "success": False,
                "summary": {"total_subdomains": 0},
                "artifacts": [],
                "raw": {"error": str(e)}
            }