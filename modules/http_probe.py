"""
HTTP Probing Module for ReconDragon

This module performs HTTP probing on hosts using httpx with asyncio concurrency.
It captures response details and optionally takes screenshots using Playwright.

Features:
- Concurrent probing with asyncio (up to 20 concurrent requests)
- HEAD request followed by GET if status 200
- Captures headers, server info, HTML title, and response time
- Screenshots of responsive web pages using Playwright (headless)
- Configurable screenshot skipping via environment variable
- Results saved as JSON
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from base import BaseModule

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright not available, screenshots will be skipped")

logger = logging.getLogger(__name__)


class HttpProbeModule(BaseModule):
    """
    HTTP probing and screenshot module for ReconDragon.

    Probes HTTP/HTTPS endpoints concurrently and captures detailed response information.
    Optionally takes screenshots of web pages using Playwright.
    """

    def __init__(self):
        self.max_concurrent = 20
        self.timeout = 10
        self.no_screenshots = os.getenv("NO_SCREENSHOTS", "false").lower() == "true"
        self.user_agent = "ReconDragon/1.0"

    @property
    def name(self) -> str:
        return "http_probe"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _get_probe_targets(self, target: str, outdir: str) -> List[str]:
        """
        Generate list of URLs to probe.

        Includes HTTP/HTTPS versions of the target and any subdomains found.

        Args:
            target: Main target domain
            outdir: Output directory to check for subdomains file

        Returns:
            List of URLs to probe
        """
        urls = []

        # Add main target
        urls.extend([f"http://{target}", f"https://{target}"])

        # Check for subdomains file from previous modules
        subdomains_file = Path(outdir) / "subdomains.txt"
        if subdomains_file.exists():
            try:
                with open(subdomains_file, 'r') as f:
                    subdomains = [line.strip() for line in f if line.strip()]

                # Add HTTP/HTTPS for each subdomain (limit to first 100 for performance)
                for subdomain in subdomains[:100]:
                    urls.extend([f"http://{subdomain}", f"https://{subdomain}"])

                logger.info(f"Found {len(subdomains)} subdomains, probing {min(len(subdomains), 100)}")
            except Exception as e:
                logger.warning(f"Could not read subdomains file: {e}")

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    async def _probe_url(self, url: str, semaphore: asyncio.Semaphore, client: httpx.AsyncClient) -> Dict[str, Any]:
        """
        Probe a single URL with HEAD then GET if successful.

        Args:
            url: URL to probe
            semaphore: Concurrency semaphore
            client: HTTP client instance

        Returns:
            Dictionary with probe results
        """
        async with semaphore:
            result = {
                "url": url,
                "status_code": None,
                "response_time": None,
                "headers": {},
                "server": None,
                "title": None,
                "error": None,
                "content_length": None,
                "final_url": None
            }

            try:
                start_time = time.time()

                # First try HEAD request
                response = await client.head(url, follow_redirects=True, timeout=self.timeout)
                response_time = time.time() - start_time

                result.update({
                    "status_code": response.status_code,
                    "response_time": round(response_time, 3),
                    "headers": dict(response.headers),
                    "final_url": str(response.url),
                    "content_length": response.headers.get("content-length")
                })

                # Extract server info
                server = response.headers.get("server")
                if server:
                    result["server"] = server

                # If HEAD successful and status 200, try GET to extract title
                if response.status_code == 200:
                    try:
                        get_response = await client.get(url, follow_redirects=True, timeout=self.timeout)
                        if get_response.status_code == 200:
                            content = get_response.text
                            title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                            if title_match:
                                result["title"] = title_match.group(1).strip()
                    except Exception as e:
                        logger.debug(f"GET request failed for {url}: {e}")

            except httpx.TimeoutException:
                result["error"] = "timeout"
            except httpx.ConnectError:
                result["error"] = "connection_failed"
            except Exception as e:
                result["error"] = str(e)
                logger.debug(f"Error probing {url}: {e}")

            return result

    async def _take_screenshot(self, url: str, screenshot_path: Path) -> bool:
        """
        Take a screenshot of a web page using Playwright.

        Args:
            url: URL to screenshot
            screenshot_path: Path to save the screenshot

        Returns:
            True if successful, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent=self.user_agent
                )
                page = await context.new_page()

                # Set reasonable timeouts
                page.set_default_timeout(30000)  # 30 seconds

                await page.goto(url, wait_until="networkidle")

                # Wait a bit for dynamic content
                await asyncio.sleep(2)

                await page.screenshot(path=str(screenshot_path), full_page=False)
                await browser.close()

                logger.debug(f"Screenshot saved: {screenshot_path}")
                return True

        except Exception as e:
            logger.debug(f"Screenshot failed for {url}: {e}")
            return False

    async def _process_screenshots(self, results: List[Dict[str, Any]], screenshots_dir: Path):
        """
        Process screenshots for successful HTTP responses.

        Args:
            results: List of probe results
            screenshots_dir: Directory to save screenshots
        """
        if self.no_screenshots or not PLAYWRIGHT_AVAILABLE:
            if self.no_screenshots:
                logger.info("Screenshots disabled via NO_SCREENSHOTS environment variable")
            return

        screenshot_tasks = []

        for result in results:
            if (result.get("status_code") == 200 and
                not result.get("error") and
                result.get("url", "").startswith(("http://", "https://"))):

                url = result["url"]
                # Create safe filename from URL
                parsed = urlparse(url)
                hostname = parsed.hostname or "unknown"
                safe_name = re.sub(r'[^\w\-_.]', '_', hostname)
                screenshot_path = screenshots_dir / f"{safe_name}.png"

                screenshot_tasks.append(self._take_screenshot(url, screenshot_path))

        if screenshot_tasks:
            logger.info(f"Taking screenshots for {len(screenshot_tasks)} responsive sites...")
            await asyncio.gather(*screenshot_tasks, return_exceptions=True)

    def run(self, target: str, outdir: str) -> Dict[str, Any]:
        """
        Execute HTTP probing on the target and related hosts.

        Probes HTTP/HTTPS endpoints concurrently, captures response details,
        and optionally takes screenshots of web pages.

        Args:
            target: The main target domain to probe
            outdir: Directory to save results and screenshots

        Returns:
            Dictionary containing probing results and metadata
        """
        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        screenshots_dir = output_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        results_file = output_dir / "http_probe_results.json"

        # Get list of URLs to probe
        urls = self._get_probe_targets(target, outdir)
        logger.info(f"Probing {len(urls)} URLs for {target}")

        # Run async probing
        async def probe_all():
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async with httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                follow_redirects=True
            ) as client:
                tasks = [self._probe_url(url, semaphore, client) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Filter out exceptions and keep only dict results
                valid_results = [r for r in results if isinstance(r, dict)]

                return valid_results

        results = asyncio.run(probe_all())

        # Process screenshots
        asyncio.run(self._process_screenshots(results, screenshots_dir))

        # Save results to JSON
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Count successful probes
        successful_probes = len([r for r in results if r.get("status_code") == 200])
        total_probes = len(results)

        logger.info(f"HTTP probing completed: {successful_probes}/{total_probes} successful")

        return {
            "module": self.name,
            "version": self.version,
            "target": target,
            "total_probes": total_probes,
            "successful_probes": successful_probes,
            "results_file": str(results_file),
            "screenshots_dir": str(screenshots_dir) if not self.no_screenshots else None,
            "screenshots_taken": len(list(screenshots_dir.glob("*.png"))) if not self.no_screenshots else 0
        }