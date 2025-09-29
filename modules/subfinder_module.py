"""
Subdomain Enumeration Module for ReconDragon

This module discovers subdomains using ProjectDiscovery's subfinder tool.
If subfinder is not available, it falls back to assetfinder.

Features:
- Automatic tool detection and fallback
- Secure subprocess execution (no shell injection)
- Configurable timeout and wordlist support
- Retry logic for reliability
- Output saved to file with count tracking
"""

import os
import subprocess
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path
from shutil import which
from base import BaseModule

logger = logging.getLogger(__name__)


class SubfinderModule(BaseModule):
    """
    Subdomain enumeration module using subfinder or assetfinder.

    This module provides subdomain discovery capabilities with automatic
    fallback between tools and robust error handling.
    """

    def __init__(self):
        self.timeout: int = int(os.getenv("SUBFINDER_TIMEOUT", "300"))  # 5 minutes default
        self.wordlist: Optional[str] = os.getenv("SUBFINDER_WORDLIST")
        self.max_retries: int = 2

    @property
    def name(self) -> str:
        return "subfinder"

    @property
    def version(self) -> str:
        return "2.0.0"

    def _check_tool_availability(self) -> str:
        """
        Check which subdomain enumeration tool is available.

        Returns:
            Tool name ('subfinder' or 'assetfinder')

        Raises:
            RuntimeError: If neither tool is available
        """
        if which("subfinder"):
            return "subfinder"
        elif which("assetfinder"):
            return "assetfinder"
        else:
            raise RuntimeError(
                "Neither subfinder nor assetfinder is installed. "
                "Please install one of these tools to use subdomain enumeration."
            )

    def _build_subfinder_args(self, target: str, output_file: str) -> list:
        """
        Build command arguments for subfinder.

        Args:
            target: Target domain to enumerate
            output_file: Path to output file

        Returns:
            List of command arguments
        """
        args = ["subfinder", "-d", target, "-o", output_file, "-timeout", str(self.timeout)]

        if self.wordlist and os.path.exists(self.wordlist):
            args.extend(["-w", self.wordlist])

        # Add silent mode and other performance options
        args.extend(["-silent", "-t", "100"])  # 100 threads

        return args

    def _build_assetfinder_args(self, target: str, output_file: str) -> list:
        """
        Build command arguments for assetfinder.

        Args:
            target: Target domain to enumerate
            output_file: Path to output file

        Returns:
            List of command arguments
        """
        # assetfinder has simpler arguments
        return ["assetfinder", "--subs-only", target]

    def _run_tool_with_retry(self, args: list, output_file: str) -> bool:
        """
        Run the enumeration tool with retry logic.

        Args:
            args: Command arguments
            output_file: Expected output file path

        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Running command (attempt {attempt + 1}): {' '.join(args)}")

                # Run with timeout to prevent hanging
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout + 30,  # Extra 30s for processing
                    check=False  # Don't raise on non-zero exit
                )

                if result.returncode == 0:
                    # Check if output file was created and has content
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        logger.info(f"Successfully completed enumeration, output: {output_file}")
                        return True
                    else:
                        logger.warning(f"Tool completed but no output file or empty: {output_file}")
                else:
                    logger.warning(f"Tool failed with return code {result.returncode}: {result.stderr}")

            except subprocess.TimeoutExpired:
                logger.warning(f"Tool timed out on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")

            if attempt < self.max_retries:
                sleep_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        return False

    def _post_process_assetfinder_output(self, tool_output: str, output_file: str):
        """
        Post-process assetfinder output to extract subdomains.

        Args:
            tool_output: Raw stdout from assetfinder
            output_file: Path to write filtered results
        """
        subdomains = set()
        for line in tool_output.splitlines():
            line = line.strip()
            if line and '.' in line:  # Basic subdomain validation
                subdomains.add(line)

        with open(output_file, 'w') as f:
            for subdomain in sorted(subdomains):
                f.write(f"{subdomain}\n")

    def run(self, target: str, outdir: str) -> Dict[str, Any]:
        """
        Execute subdomain enumeration for the target domain.

        Attempts to use subfinder first, falls back to assetfinder if needed.
        Results are saved to a file and returned with metadata.

        Args:
            target: The target domain to enumerate subdomains for
            outdir: Directory to save enumeration results

        Returns:
            Dictionary containing enumeration results and metadata

        Raises:
            ValueError: If target is invalid
            RuntimeError: If no enumeration tool is available
        """
        if not target or '.' not in target:
            raise ValueError(f"Invalid target domain: {target}")

        # Ensure output directory exists
        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "subdomains.txt"

        try:
            # Determine which tool to use
            tool = self._check_tool_availability()
            logger.info(f"Using {tool} for subdomain enumeration of {target}")

            # Build command arguments
            if tool == "subfinder":
                args = self._build_subfinder_args(target, str(output_file))
            else:  # assetfinder
                args = self._build_assetfinder_args(target, str(output_file))

            # Run the tool with retry logic
            success = self._run_tool_with_retry(args, str(output_file))

            if not success:
                logger.error(f"All attempts failed for {target}")
                return {
                    "module": self.name,
                    "version": self.version,
                    "target": target,
                    "count": 0,
                    "file": str(output_file),
                    "status": "failed",
                    "error": "Enumeration failed after retries"
                }

            # Count discovered subdomains
            if output_file.exists():
                with open(output_file, 'r') as f:
                    lines = f.readlines()
                    count = len([line.strip() for line in lines if line.strip()])
            else:
                count = 0

            logger.info(f"Discovered {count} subdomains for {target}")

            return {
                "module": self.name,
                "version": self.version,
                "target": target,
                "count": count,
                "file": str(output_file),
                "status": "completed",
                "tool_used": tool
            }

        except Exception as e:
            logger.error(f"Error during subdomain enumeration: {e}")
            return {
                "module": self.name,
                "version": self.version,
                "target": target,
                "count": 0,
                "file": str(output_file) if output_file.exists() else None,
                "status": "error",
                "error": str(e)
            }