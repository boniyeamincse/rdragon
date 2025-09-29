"""
Nmap Port Scanning Module for ReconDragon

Performs comprehensive port scanning using nmap with XML output parsing.
"""

import json
import logging
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List

from base import BaseModule

logger = logging.getLogger(__name__)


class NmapModule(BaseModule):
    """
    Nmap-based port scanning module for ReconDragon.

    Performs comprehensive TCP port scanning with service and OS detection.
    """

    def __init__(self):
        self.timeout = 1800  # 30 minutes timeout for thorough scans

    @property
    def name(self) -> str:
        return "nmap"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _parse_nmap_xml(self, xml_file: Path) -> Dict[str, Any]:
        """Parse nmap XML output into structured data."""
        if not xml_file.exists():
            return {"ports": [], "services": [], "os": None, "hosts": []}

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            results = {
                "ports": [],
                "services": [],
                "os": None,
                "hosts": []
            }

            # Parse hosts
            for host in root.findall('host'):
                host_info = {"ip": None, "hostname": None, "state": None}

                address = host.find('address')
                if address is not None:
                    host_info["ip"] = address.get('addr')

                hostname_elem = host.find('hostnames/hostname')
                if hostname_elem is not None:
                    host_info["hostname"] = hostname_elem.get('name')

                status = host.find('status')
                if status is not None:
                    host_info["state"] = status.get('state')

                results["hosts"].append(host_info)

                # Parse ports
                ports_elem = host.find('ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        port_info = {
                            "port": int(port.get('portid')),
                            "protocol": port.get('protocol'),
                            "state": port.find('state').get('state') if port.find('state') is not None else None,
                            "service": None,
                            "version": None
                        }

                        service = port.find('service')
                        if service is not None:
                            port_info["service"] = service.get('name')
                            port_info["version"] = service.get('version', '')

                        if port_info["state"] == "open":
                            results["ports"].append(port_info)
                            results["services"].append(port_info)

            # Parse OS detection
            for host in root.findall('host'):
                os_elem = host.find('os')
                if os_elem is not None:
                    osmatch = os_elem.find('osmatch')
                    if osmatch is not None:
                        results["os"] = osmatch.get('name')

            return results

        except (ET.ParseError, FileNotFoundError) as e:
            logger.error(f"Failed to parse nmap XML: {e}")
            return {"ports": [], "services": [], "os": None, "hosts": []}

    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute nmap port scanning.

        Args:
            target: Target IP or domain
            outdir: Output directory
            execute: Whether to actually run the scan
            **kwargs: Additional options (timing, scripts, etc.)

        Returns:
            Dict with standardized module results
        """
        start_time = time.time()

        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        xml_file = output_dir / f"nmap_{target.replace('.', '_').replace('/', '_')}.xml"

        # Build nmap command
        cmd = [
            "nmap",
            "-sV",  # Version detection
            "-sC",  # Default scripts
            "-O",   # OS detection
            "-p-",  # All ports
            "-T4",  # Aggressive timing
            "-oX", str(xml_file),  # XML output
            target
        ]

        # Add optional vulnerability scanning if requested
        if kwargs.get('vulners', False):
            cmd.insert(-1, "--script")
            cmd.insert(-1, "vulners")

        success = False
        error_msg = None
        raw_output = None

        if execute:
            try:
                logger.info(f"Running nmap scan on {target}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=True
                )
                success = True
                raw_output = result.stdout
                logger.info("Nmap scan completed successfully")
            except subprocess.TimeoutExpired:
                error_msg = "Nmap scan timed out"
                logger.error(error_msg)
            except subprocess.CalledProcessError as e:
                error_msg = f"Nmap failed: {e.stderr}"
                logger.error(error_msg)
            except FileNotFoundError:
                error_msg = "nmap binary not found. Please install nmap."
                logger.error(error_msg)
        else:
            # Dry-run
            logger.info(f"Dry-run: Would execute {' '.join(cmd)}")
            success = True

        # Parse results
        parsed_results = self._parse_nmap_xml(xml_file)

        end_time = time.time()

        # Generate summary
        summary = {
            "target": target,
            "open_ports": len(parsed_results["ports"]),
            "hosts_discovered": len(parsed_results["hosts"]),
            "os_detected": parsed_results["os"],
            "scan_duration": round(end_time - start_time, 2)
        }

        if error_msg:
            summary["error"] = error_msg

        # Artifacts
        artifacts = []
        if xml_file.exists():
            artifacts.append(str(xml_file))

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