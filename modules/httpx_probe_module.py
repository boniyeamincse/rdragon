"""
HTTPX Probe Module for ReconDragon

Async HTTP probing with optional screenshot capture.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urljoin, urlparse

import httpx

from base import BaseModule

logger = logging.getLogger(__name__)


class HttpxProbeModule(BaseModule):
    """
    Async HTTP probing module using httpx.

    Probes HTTP/HTTPS endpoints concurrently with optional screenshot capture.
    """

    def __init__(self):
        self.max_concurrent = 20
        self.timeout = 10
        self.user_agent = "ReconDragon/1.0"

    @property
    def name(self) -> str:
        return "httpx_probe"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _get_probe_targets(self, target: str) -> List[str]:
        """Generate URLs to probe."""
        urls = [f"http://{target}", f"https://{target}"]
        # In a full implementation, you might check for subdomains from previous modules
        return urls

    async def _probe_url(self, url: str, semaphore: asyncio.Semaphore, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Probe a single URL."""
        async with semaphore:
            result = {
                "url": url,
                "status_code": None,
                "response_time": None,
                "headers": {},
                "server": None,
                "title": None,
                "error": None,
                "content_length": None
            }

            try:
                start_time = time.time()
                response = await client.get(url, follow_redirects=True, timeout=self.timeout)
                response_time = time.time() - start_time

                result.update({
                    "status_code": response.status_code,
                    "response_time": round(response_time, 3),
                    "headers": dict(response.headers),
                    "content_length": response.headers.get("content-length")
                })

                # Extract server
                server = response.headers.get("server")
                if server:
                    result["server"] = server

                # Extract title from HTML if available
                if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
                    content = response.text
                    import re
                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                    if title_match:
                        result["title"] = title_match.group(1).strip()

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                result["error"] = str(type(e).__name__)
            except Exception as e:
                result["error"] = str(e)
                logger.debug(f"Error probing {url}: {e}")

            return result

    async def _take_screenshot_placeholder(self, url: str, screenshot_path: Path) -> bool:
        """
        Placeholder for screenshot capture.

        In production, integrate with playwright or similar.
        For now, this is a no-op that returns False.
        """
        logger.info(f"Screenshot capture not implemented for {url}")
        # TODO: Implement screenshot capture using playwright
        return False

    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute HTTP probing.

        Args:
            target: Target domain
            outdir: Output directory
            execute: Whether to actually run the probes
            **kwargs: Additional options (screenshots, etc.)

        Returns:
            Dict with standardized module results
        """
        start_time = time.time()

        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results_file = output_dir / "httpx_probe_results.json"
        screenshots_dir = output_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        urls = self._get_probe_targets(target)

        success = False
        results = []
        error_msg = None

        if execute:
            try:
                logger.info(f"Probing {len(urls)} URLs for {target}")

                async def probe_all():
                    semaphore = asyncio.Semaphore(self.max_concurrent)
                    async with httpx.AsyncClient(
                        headers={"User-Agent": self.user_agent},
                        follow_redirects=True
                    ) as client:
                        tasks = [self._probe_url(url, semaphore, client) for url in urls]
                        return await asyncio.gather(*tasks, return_exceptions=True)

                raw_results = asyncio.run(probe_all())
                results = [r for r in raw_results if isinstance(r, dict)]

                # Screenshot capture (placeholder)
                if kwargs.get('screenshots', False):
                    screenshot_tasks = []
                    for result in results:
                        if result.get("status_code") == 200:
                            url = result["url"]
                            parsed = urlparse(url)
                            hostname = parsed.hostname or "unknown"
                            safe_name = hostname.replace('.', '_')
                            screenshot_path = screenshots_dir / f"{safe_name}.png"
                            # In real implementation, this would be async
                            asyncio.run(self._take_screenshot_placeholder(url, screenshot_path))

                success = True
                logger.info(f"HTTP probing completed: {len(results)} URLs probed")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"HTTP probing failed: {e}")
        else:
            # Dry-run
            logger.info(f"Dry-run: Would probe {len(urls)} URLs for {target}")
            success = True

        # Save results
        if results:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)

        end_time = time.time()

        # Count successful probes
        successful_probes = len([r for r in results if r.get("status_code") == 200])

        summary = {
            "target": target,
            "urls_probed": len(urls),
            "successful_probes": successful_probes,
            "total_probes": len(results),
            "scan_duration": round(end_time - start_time, 2)
        }

        if error_msg:
            summary["error"] = error_msg

        artifacts = []
        if results_file.exists():
            artifacts.append(str(results_file))
        if any(screenshots_dir.glob("*.png")):
            artifacts.append(str(screenshots_dir))

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