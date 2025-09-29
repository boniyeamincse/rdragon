"""
Tests for HarvesterModule

This module tests the HarvesterModule functionality using pytest.
"""

import pytest
import tempfile
import json
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from modules.harvester_module import HarvesterModule


@pytest.fixture
def harvester_module():
    """Fixture for HarvesterModule instance."""
    return HarvesterModule()


@pytest.fixture
def temp_outdir():
    """Fixture for temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestHarvesterModule:
    """Test cases for HarvesterModule."""

    def test_module_properties(self, harvester_module):
        """Test module name and version."""
        assert harvester_module.name == "harvester"
        assert harvester_module.version == "1.0.0"

    def test_check_tool_availability(self, harvester_module):
        """Test tool availability check."""
        with patch('shutil.which', return_value='/usr/bin/theHarvester'):
            assert harvester_module._check_tool_availability() is True

        with patch('shutil.which', return_value=None):
            assert harvester_module._check_tool_availability() is False

    def test_build_harvester_command(self, harvester_module):
        """Test building theHarvester command."""
        cmd = harvester_module._build_harvester_command("example.com", "/tmp/out.json", ["google", "bing"], 50)
        expected = [
            "theHarvester", "-d", "example.com", "-f", "json", "-o", "/tmp/out.json",
            "-l", "50", "-t", "300", "-b", "google,bing"
        ]
        assert cmd == expected

    def test_parse_harvester_output(self, harvester_module, temp_outdir):
        """Test parsing harvester JSON output."""
        output_file = Path(temp_outdir) / "test.json"
        test_data = {
            "emails": ["test@example.com"],
            "hosts": ["www.example.com"],
            "linkedin_links": ["https://linkedin.com/company/example"],
            "twitter_links": ["https://twitter.com/example"]
        }
        with open(output_file, 'w') as f:
            json.dump(test_data, f)

        parsed = harvester_module._parse_harvester_output(str(output_file))
        assert parsed == test_data

    def test_parse_harvester_output_missing_file(self, harvester_module):
        """Test parsing when output file doesn't exist."""
        parsed = harvester_module._parse_harvester_output("/nonexistent/file.json")
        assert parsed == {"emails": [], "hosts": [], "linkedin_links": [], "twitter_links": []}

    @patch('shutil.which')
    def test_run_dry_mode(self, mock_which, harvester_module, temp_outdir):
        """Test dry-run mode."""
        mock_which.return_value = True

        result = harvester_module.run("example.com", temp_outdir, execute=False, sources=["google"], limit=100)

        assert result["module"] == "harvester"
        assert result["target"] == "example.com"
        assert result["status"] == "dry-run"
        assert "plan" in result["raw"]
        assert "theharvester_command" in result["raw"]["plan"]
        assert "enrichment_apis" in result["raw"]["plan"]
        assert "note" in result["raw"]

    @patch('shutil.which')
    @patch('subprocess.run')
    @patch('asyncio.run')
    def test_run_execute_mode_success(self, mock_asyncio, mock_run, mock_which, harvester_module, temp_outdir):
        """Test execute mode with successful execution."""
        mock_which.return_value = True

        # Mock subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Mock harvester output
        output_file = Path(temp_outdir) / "harvester_results.json"
        harvester_data = {
            "emails": ["test@example.com"],
            "hosts": ["www.example.com"],
            "linkedin_links": ["https://linkedin.com/company/example"]
        }
        with open(output_file, 'w') as f:
            json.dump(harvester_data, f)

        # Mock enrichment
        mock_asyncio.return_value = (
            ["sub.example.com"],  # crt domains
            {"emails": ["new@example.com"], "names": ["John Doe"]},  # hunter
            {"test@example.com": ["Breach1"]}  # hibp
        )

        result = harvester_module.run("example.com", temp_outdir, execute=True)

        assert result["status"] == "completed"
        assert "results" in result
        assert result["results"]["emails"] == ["test@example.com", "new@example.com"]
        assert result["results"]["hosts"] == ["www.example.com", "sub.example.com"]
        assert result["results"]["possible_employee_names"] == ["John Doe"]
        assert result["results"]["notable_findings"] == ["Email test@example.com found in breaches: Breach1"]

    @patch('shutil.which')
    def test_run_execute_mode_no_tool(self, mock_which, harvester_module, temp_outdir):
        """Test execute mode when theHarvester is not available."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError, match="theHarvester is not installed"):
            harvester_module.run("example.com", temp_outdir, execute=True)

    def test_run_invalid_target(self, harvester_module, temp_outdir):
        """Test with invalid target."""
        with pytest.raises(ValueError, match="Invalid target domain"):
            harvester_module.run("invalid", temp_outdir, execute=False)

    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_enrich_crt_sh(self, mock_client, harvester_module, temp_outdir):
        """Test crt.sh enrichment."""
        cache_dir = Path(temp_outdir) / "cache"
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"common_name": "sub1.example.com", "name_value": "sub2.example.com\nsub3.example.com"}
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        domains = await harvester_module._enrich_crt_sh("example.com", cache_dir)
        assert set(domains) == {"sub1.example.com", "sub2.example.com", "sub3.example.com"}

    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_enrich_hunter_io(self, mock_client, harvester_module, temp_outdir):
        """Test hunter.io enrichment."""
        harvester_module.hunter_api_key = "test_key"
        cache_dir = Path(temp_outdir) / "cache"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "emails": [
                    {"value": "john@example.com", "first_name": "John", "last_name": "Doe"}
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        data = await harvester_module._enrich_hunter_io("example.com", cache_dir)
        assert data["emails"] == ["john@example.com"]
        assert data["names"] == ["John Doe"]

    @pytest.mark.asyncio
    async def test_enrich_hunter_io_no_key(self, harvester_module, temp_outdir):
        """Test hunter.io enrichment without API key."""
        harvester_module.hunter_api_key = None
        cache_dir = Path(temp_outdir) / "cache"

        data = await harvester_module._enrich_hunter_io("example.com", cache_dir)
        assert data == {"emails": [], "names": []}

    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_enrich_haveibeenpwned(self, mock_client, harvester_module, temp_outdir):
        """Test HaveIBeenPwned enrichment."""
        harvester_module.haveibeenpwned_api_key = "test_key"
        cache_dir = Path(temp_outdir) / "cache"

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"Name": "Breach1"}, {"Name": "Breach2"}
        ]
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        breaches = await harvester_module._enrich_haveibeenpwned(["test@example.com"], cache_dir)
        assert breaches["test@example.com"] == ["Breach1", "Breach2"]