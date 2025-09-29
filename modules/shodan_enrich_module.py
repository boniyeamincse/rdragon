"""
Shodan Enrichment Module for ReconDragon

Queries Shodan API for IP/host information with caching.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

from base import BaseModule

logger = logging.getLogger(__name__)


class ShodanEnrichModule(BaseModule):
    """
    Shodan API enrichment module for ReconDragon.

    Queries Shodan for detailed host information with result caching.
    """

    def __init__(self):
        self.api_key = os.getenv("SHODAN_API_KEY")  # TODO: Set SHODAN_API_KEY environment variable
        self.base_url = "https://api.shodan.io"
        self.cache_dir = None  # Will be set in run()

    @property
    def name(self) -> str:
        return "shodan_enrich"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _get_cache_key(self, target: str) -> str:
        """Generate cache key for target."""
        return hashlib.md5(target.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result if available and not expired."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Check if cache is still valid (24 hours)
            if time.time() - data.get('cached_at', 0) < 86400:
                return data['result']
            else:
                # Cache expired, remove it
                cache_file.unlink()
                return None
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache the result."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        data = {
            'cached_at': time.time(),
            'result': result
        }
        with open(cache_file, 'w') as f:
            json.dump(data, f)

    async def _query_shodan(self, target: str) -> Dict[str, Any]:
        """Query Shodan API for target information."""
        if not self.api_key:
            raise ValueError("SHODAN_API_KEY environment variable not set")

        url = f"{self.base_url}/shodan/host/{target}"
        params = {'key': self.api_key}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute Shodan enrichment.

        Args:
            target: Target IP address
            outdir: Output directory
            execute: Whether to actually query the API
            **kwargs: Additional options

        Returns:
            Dict with standardized module results
        """
        start_time = time.time()

        if not self.api_key:
            logger.warning("SHODAN_API_KEY not set - add to environment variables")

        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = output_dir / "shodan_cache"
        self.cache_dir.mkdir(exist_ok=True)

        results_file = output_dir / "shodan_results.json"
        cache_key = self._get_cache_key(target)

        success = False
        result = None
        error_msg = None
        cached = False

        # Check cache first
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            result = cached_result
            success = True
            cached = True
            logger.info(f"Using cached Shodan result for {target}")
        elif execute:
            try:
                logger.info(f"Querying Shodan API for {target}")
                # Run async query
                import asyncio
                result = asyncio.run(self._query_shodan(target))
                self._cache_result(cache_key, result)
                success = True
                logger.info(f"Shodan query completed for {target}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    error_msg = "Target not found in Shodan"
                else:
                    error_msg = f"Shodan API error: {e.response.status_code}"
                logger.error(error_msg)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Shodan query failed: {e}")
        else:
            # Dry-run
            logger.info(f"Dry-run: Would query Shodan for {target}")
            success = True

        # Save results
        if result:
            with open(results_file, 'w') as f:
                json.dump(result, f, indent=2)

        end_time = time.time()

        summary = {
            "target": target,
            "data_retrieved": bool(result),
            "cached": cached,
            "query_duration": round(end_time - start_time, 2)
        }

        if error_msg:
            summary["error"] = error_msg

        # Extract key info for summary
        if result:
            summary.update({
                "ports": len(result.get('data', [])),
                "hostnames": result.get('hostnames', []),
                "org": result.get('org'),
                "country": result.get('country_name')
            })

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
            "raw": None
        }