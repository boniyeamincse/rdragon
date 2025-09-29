"""
Unit tests for HttpxProbeModule.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from modules.httpx_probe_module import HttpxProbeModule


class TestHttpxProbeModule:
    @pytest.fixture
    def module(self):
        return HttpxProbeModule()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_name_property(self, module):
        assert module.name == "httpx_probe"

    def test_version_property(self, module):
        assert module.version == "1.0.0"

    def test_dry_run_mode(self, module, temp_dir):
        """Test dry-run doesn't execute requests."""
        result = module.run("example.com", str(temp_dir), execute=False)

        assert result["module"] == "httpx_probe"
        assert result["success"] is True
        assert result["summary"]["urls_probed"] == 2  # http and https

    @patch('asyncio.run')
    def test_successful_probe(self, mock_asyncio_run, module, temp_dir):
        """Test successful HTTP probing."""
        # Mock the async probe results
        mock_results = [
            {"url": "http://example.com", "status_code": 200, "response_time": 0.5},
            {"url": "https://example.com", "status_code": 200, "response_time": 0.7}
        ]
        mock_asyncio_run.return_value = mock_results

        result = module.run("example.com", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["successful_probes"] == 2
        assert result["summary"]["total_probes"] == 2

    @patch('asyncio.run')
    def test_probe_with_errors(self, mock_asyncio_run, module, temp_dir):
        """Test handling of probe errors."""
        mock_results = [
            {"url": "http://example.com", "status_code": 200, "response_time": 0.5},
            {"url": "https://example.com", "error": "TimeoutException"}
        ]
        mock_asyncio_run.return_value = mock_results

        result = module.run("example.com", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["successful_probes"] == 1
        assert result["summary"]["total_probes"] == 2