"""
Harvester Module for ReconDragon

This module wraps theHarvester tool and adds OSINT enrichment capabilities.
It discovers emails, hosts, and other OSINT data from various sources.

Features:
- Integration with theHarvester for comprehensive OSINT gathering
- Additional enrichment via crt.sh, hunter.io, and other APIs
- Caching to avoid API rate limits
- Privacy-aware with data retention notes
- Configurable sources and limits
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import subprocess
import time
from shutil import which

import httpx

from base import BaseModule

logger = logging.getLogger(__name__)


class HarvesterModule(BaseModule):
    """
    OSINT harvesting module using theHarvester with additional enrichment.

    This module provides comprehensive OSINT data collection with API enrichment
    and caching capabilities.
    """

    def __init__(self):
        self.timeout: int = int(os.getenv("HARVESTER_TIMEOUT", "300"))  # 5 minutes default
        self.cache_dir: str = "cache"
        self.max_retries: int = 2

        # API keys from environment
        self.hunter_api_key: Optional[str] = os.getenv("HUNTER_API_KEY")
        self.haveibeenpwned_api_key: Optional[str] = os.getenv("HIBP_API_KEY")

    @property
    def name(self) -> str:
        return "harvester"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _check_tool_availability(self) -> bool:
        """Check if theHarvester is available."""
        return which("theHarvester") is not None

    def _build_harvester_command(self, target: str, output_file: str, sources: List[str] = None, limit: int = 100) -> List[str]:
        """Build theHarvester command arguments."""
        args = [
            "theHarvester",
            "-d", target,
            "-f", "json",
            "-o", output_file,
            "-l", str(limit),
            "-t", str(self.timeout)
        ]

        if sources:
            args.extend(["-b", ",".join(sources)])

        return args

    def _run_command_with_retry(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run command with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Running command (attempt {attempt + 1}): {' '.join(args)}")
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout + 30,
                    check=False
                )
                if result.returncode == 0:
                    return result
                logger.warning(f"Command failed with return code {result.returncode}: {result.stderr}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Command timed out on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")

            if attempt < self.max_retries:
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        raise RuntimeError("All attempts to run theHarvester failed")

    def _parse_harvester_output(self, output_file: str) -> Dict[str, Any]:
        """Parse theHarvester JSON output."""
        if not Path(output_file).exists():
            return {"emails": [], "hosts": [], "linkedin_links": [], "twitter_links": []}

        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to parse harvester output: {e}")
            return {"emails": [], "hosts": [], "linkedin_links": [], "twitter_links": []}

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached_response(self, cache_path: Path, max_age: int = 3600) -> Optional[Dict]:
        """Get cached response if valid."""
        if not cache_path.exists():
            return None

        if time.time() - cache_path.stat().st_mtime > max_age:
            return None

        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _cache_response(self, cache_path: Path, data: Dict):
        """Cache API response."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(data, f)

    async def _enrich_crt_sh(self, target: str, cache_dir: Path) -> List[str]:
        """Enrich with certificate transparency from crt.sh."""
        url = f"https://crt.sh/?q={target}&output=json"
        cache_key = self._get_cache_key(url)
        cache_path = cache_dir / f"crt_sh_{cache_key}.json"

        cached = self._get_cached_response(cache_path)
        if cached:
            return cached.get("domains", [])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            domains = []
            for cert in data:
                if "common_name" in cert:
                    domains.append(cert["common_name"])
                if "name_value" in cert and cert["name_value"]:
                    domains.extend(cert["name_value"].split("\n"))

            domains = list(set(domains))  # Unique
            self._cache_response(cache_path, {"domains": domains})
            return domains
        except Exception as e:
            logger.error(f"crt.sh enrichment failed: {e}")
            return []

    async def _enrich_hunter_io(self, target: str, cache_dir: Path) -> Dict[str, Any]:
        """Enrich with hunter.io data."""
        if not self.hunter_api_key:
            return {"emails": [], "names": []}

        url = f"https://api.hunter.io/v2/domain-search?domain={target}&api_key={self.hunter_api_key}"
        cache_key = self._get_cache_key(url)
        cache_path = cache_dir / f"hunter_io_{cache_key}.json"

        cached = self._get_cached_response(cache_path)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            emails = []
            names = []
            if "data" in data and "emails" in data["data"]:
                for email_data in data["data"]["emails"]:
                    emails.append(email_data.get("value", ""))
                    if "first_name" in email_data and "last_name" in email_data:
                        names.append(f"{email_data['first_name']} {email_data['last_name']}")

            result = {"emails": emails, "names": names}
            self._cache_response(cache_path, result)
            return result
        except Exception as e:
            logger.error(f"Hunter.io enrichment failed: {e}")
            return {"emails": [], "names": []}

    async def _enrich_haveibeenpwned(self, emails: List[str], cache_dir: Path) -> Dict[str, List[str]]:
        """Check emails against HaveIBeenPwned."""
        if not self.haveibeenpwned_api_key:
            return {}

        breaches = {}
        for email in emails[:10]:  # Limit to first 10 emails
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"
            headers = {"hibp-api-key": self.haveibeenpwned_api_key}
            cache_key = self._get_cache_key(url)
            cache_path = cache_dir / f"hibp_{cache_key}.json"

            cached = self._get_cached_response(cache_path)
            if cached:
                breaches[email] = cached.get("breaches", [])
                continue

            try:
                async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        breach_names = [breach["Name"] for breach in data]
                        breaches[email] = breach_names
                        self._cache_response(cache_path, {"breaches": breach_names})
                    elif response.status_code == 404:
                        breaches[email] = []
                        self._cache_response(cache_path, {"breaches": []})
                    else:
                        logger.warning(f"HIBP API error for {email}: {response.status_code}")
            except Exception as e:
                logger.error(f"HIBP check failed for {email}: {e}")

        return breaches

    def run(self, target: str, outdir: str, execute: bool = False, sources: List[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Execute OSINT harvesting for the target domain.

        Args:
            target: Target domain to harvest OSINT for
            outdir: Directory to save results and cache
            execute: Whether to actually run theHarvester and API calls
            sources: List of sources for theHarvester (optional)
            limit: Result limit for theHarvester

        Returns:
            Dictionary containing harvesting results
        """
        if not target or '.' not in target:
            raise ValueError(f"Invalid target domain: {target}")

        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = output_dir / self.cache_dir

        output_file = output_dir / "harvester_results.json"

        # Plan for dry-run
        plan = {
            "theharvester_command": self._build_harvester_command(target, str(output_file), sources, limit),
            "enrichment_apis": []
        }

        if self.hunter_api_key:
            plan["enrichment_apis"].append(f"Hunter.io API call for {target}")
        else:
            plan["enrichment_apis"].append("Hunter.io API (skipped: no API key)")

        plan["enrichment_apis"].append(f"crt.sh certificate transparency for {target}")

        if self.haveibeenpwned_api_key:
            plan["enrichment_apis"].append("HaveIBeenPwned breach checks (for discovered emails)")
        else:
            plan["enrichment_apis"].append("HaveIBeenPwned (skipped: no API key)")

        if not execute:
            return {
                "module": self.name,
                "version": self.version,
                "target": target,
                "status": "dry-run",
                "raw": {
                    "plan": plan,
                    "note": "Data retention: All collected OSINT data should be stored securely and deleted after analysis. Ensure compliance with privacy laws and obtain consent where required."
                }
            }

        # Execute mode
        if not self._check_tool_availability():
            raise RuntimeError("theHarvester is not installed. Please install it to use this module.")

        # Run theHarvester
        try:
            args = self._build_harvester_command(target, str(output_file), sources, limit)
            self._run_command_with_retry(args)
            harvester_data = self._parse_harvester_output(str(output_file))
        except Exception as e:
            logger.error(f"theHarvester execution failed: {e}")
            return {
                "module": self.name,
                "version": self.version,
                "target": target,
                "status": "error",
                "error": str(e),
                "raw": {
                    "plan": plan,
                    "note": "Data retention: All collected OSINT data should be stored securely and deleted after analysis. Ensure compliance with privacy laws and obtain consent where required."
                }
            }

        # Enrichment
        import asyncio
        async def enrich():
            crt_domains = await self._enrich_crt_sh(target, cache_dir)
            hunter_data = await self._enrich_hunter_io(target, cache_dir)
            hibp_breaches = await self._enrich_haveibeenpwned(harvester_data.get("emails", []) + hunter_data.get("emails", []), cache_dir)
            return crt_domains, hunter_data, hibp_breaches

        try:
            crt_domains, hunter_data, hibp_breaches = asyncio.run(enrich())
        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            crt_domains, hunter_data, hibp_breaches = [], {"emails": [], "names": []}, {}

        # Combine results
        all_emails = list(set(harvester_data.get("emails", []) + hunter_data.get("emails", [])))
        all_hosts = list(set(harvester_data.get("hosts", []) + crt_domains))
        linked_domains = list(set(harvester_data.get("linkedin_links", [])))  # Assuming linkedin_links are domains
        employee_names = hunter_data.get("names", [])

        notable_findings = []
        for email, breaches in hibp_breaches.items():
            if breaches:
                notable_findings.append(f"Email {email} found in breaches: {', '.join(breaches)}")

        return {
            "module": self.name,
            "version": self.version,
            "target": target,
            "status": "completed",
            "results": {
                "emails": all_emails,
                "hosts": all_hosts,
                "linked_domains": linked_domains,
                "possible_employee_names": employee_names,
                "notable_findings": notable_findings
            },
            "counts": {
                "emails": len(all_emails),
                "hosts": len(all_hosts),
                "linked_domains": len(linked_domains),
                "employee_names": len(employee_names),
                "findings": len(notable_findings)
            },
            "raw": {
                "harvester_output": harvester_data,
                "crt_sh_domains": crt_domains,
                "hunter_io_data": hunter_data,
                "hibp_breaches": hibp_breaches,
                "plan": plan,
                "note": "Data retention: All collected OSINT data should be stored securely and deleted after analysis. Ensure compliance with privacy laws and obtain consent where required."
            }
        }