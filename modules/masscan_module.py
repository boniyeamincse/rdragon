"""
Masscan Module for ReconDragon

Fast port scanning using masscan with JSON output.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

from base import BaseModule

logger = logging.getLogger(__name__)


class MasscanModule(BaseModule):
    """
    Masscan port scanning module for ReconDragon.

    Performs fast TCP/UDP port scanning using masscan.
    """

    def __init__(self):
        self.timeout = 600  # 10 minutes timeout
        self.rate = 100000  # packets per second
        self.ports = "1-65535"  # Default port range

    @property
    def name(self) -> str:
        return "masscan"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _parse_masscan_output(self, output_file: Path) -> List[Dict[str, Any]]:
        """Parse masscan JSON output."""
        if not output_file.exists():
            return []

        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to parse masscan output: {e}")
            return []

    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute masscan port scanning.

        Args:
            target: Target IP or CIDR range
            outdir: Output directory
            execute: Whether to actually run the scan
            **kwargs: Additional options (ports, rate, etc.)

        Returns:
            Dict with standardized module results
        """
        start_time = time.time()

        # Update settings from kwargs
        ports = kwargs.get('ports', self.ports)
        rate = kwargs.get('rate', self.rate)

        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results_file = output_dir / "masscan_results.json"

        # Prepare command
        cmd = [
            "masscan",
            "--ports", ports,
            "--rate", str(rate),
            "--output-format", "json",
            "--output-file", str(results_file),
            target
        ]

        success = False
        error_msg = None
        raw_output = None

        if execute:
            try:
                logger.info(f"Running masscan on {target} with ports {ports}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=True
                )
                success = True
                raw_output = result.stdout
                logger.info("Masscan completed successfully")
            except subprocess.TimeoutExpired:
                error_msg = "Masscan scan timed out"
                logger.error(error_msg)
            except subprocess.CalledProcessError as e:
                error_msg = f"Masscan failed: {e.stderr}"
                logger.error(error_msg)
            except FileNotFoundError:
                error_msg = "masscan binary not found. Please install masscan."
                logger.error(error_msg)
        else:
            # Dry-run: just log what would be done
            logger.info(f"Dry-run: Would execute {' '.join(cmd)}")
            success = True  # Dry-run is considered successful

        # Parse results if available
        scan_results = self._parse_masscan_output(results_file)

        end_time = time.time()

        # Count open ports
        open_ports = len(scan_results) if scan_results else 0

        # Generate summary
        summary = {
            "target": target,
            "ports_scanned": ports,
            "open_ports_found": open_ports,
            "scan_duration": round(end_time - start_time, 2),
            "rate": rate
        }

        if error_msg:
            summary["error"] = error_msg

        # Artifacts
        artifacts = []
        if results_file.exists():
            artifacts.append(str(results_file))

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