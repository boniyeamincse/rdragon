"""
Unit tests for ShodanEnrichModule.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from modules.shodan_enrich_module import ShodanEnrichModule


class TestShodanEnrichModule:
    @pytest.fixture
    def module(self):
        return ShodanEnrichModule()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_name_property(self, module):
        assert module.name == "shodan_enrich"

    def test_version_property(self, module):
        assert module.version == "1.0.0"

    @patch.dict('os.environ', {'SHODAN_API_KEY': 'test_key'})
    def test_dry_run_mode(self, module, temp_dir):
        """Test dry-run doesn't execute API calls."""
        result = module.run("192.168.1.1", str(temp_dir), execute=False)

        assert result["module"] == "shodan_enrich"
        assert result["success"] is True

    @patch.dict('os.environ', {'SHODAN_API_KEY': 'test_key'})
    @patch('asyncio.run')
    def test_successful_query(self, mock_asyncio_run, module, temp_dir):
        """Test successful Shodan API query."""
        mock_result = {
            "ip_str": "192.168.1.1",
            "hostnames": ["example.com"],
            "org": "Test Org",
            "country_name": "Test Country",
            "data": [{"port": 80}, {"port": 443}]
        }
        mock_asyncio_run.return_value = mock_result

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["data_retrieved"] is True
        assert result["summary"]["ports"] == 2
        assert result["summary"]["org"] == "Test Org"

    @patch.dict('os.environ', {'SHODAN_API_KEY': ''})
    def test_missing_api_key(self, module, temp_dir):
        """Test handling of missing API key."""
        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is False
        assert "SHODAN_API_KEY" in result["summary"]["error"]

    @patch.dict('os.environ', {'SHODAN_API_KEY': 'test_key'})
    def test_cached_result(self, module, temp_dir):
        """Test using cached results."""
        # Pre-populate cache
        cache_key = module._get_cache_key("192.168.1.1")
        cache_file = temp_dir / "shodan_cache" / f"{cache_key}.json"
        cache_file.parent.mkdir(exist_ok=True)

        cached_data = {
            "cached_at": 1234567890,  # Future timestamp
            "result": {"ip_str": "192.168.1.1", "hostnames": ["cached.com"]}
        }
        with open(cache_file, 'w') as f:
            json.dump(cached_data, f)

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["cached"] is True
        assert result["summary"]["hostnames"] == ["cached.com"]