"""
Unit tests for MasscanModule.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from modules.masscan_module import MasscanModule


class TestMasscanModule:
    @pytest.fixture
    def module(self):
        return MasscanModule()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_name_property(self, module):
        assert module.name == "masscan"

    def test_version_property(self, module):
        assert module.version == "1.0.0"

    def test_dry_run_mode(self, module, temp_dir):
        """Test dry-run doesn't execute subprocess."""
        result = module.run("192.168.1.1", str(temp_dir), execute=False)

        assert result["module"] == "masscan"
        assert result["success"] is True
        assert "Dry-run" in str(result.get("summary", {}).get("error", ""))
        assert result["artifacts"] == []

    @patch('subprocess.run')
    def test_successful_scan(self, mock_subprocess, module, temp_dir):
        """Test successful masscan execution."""
        # Mock successful subprocess run
        mock_process = MagicMock()
        mock_process.stdout = ""
        mock_subprocess.return_value = mock_process

        # Create mock JSON output file
        results_file = temp_dir / "masscan_results.json"
        mock_data = [{"ip": "192.168.1.1", "ports": [80, 443]}]
        with open(results_file, 'w') as f:
            json.dump(mock_data, f)

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["open_ports_found"] == 2
        assert str(results_file) in result["artifacts"]

    @patch('subprocess.run')
    def test_scan_timeout(self, mock_subprocess, module, temp_dir):
        """Test handling of scan timeout."""
        from subprocess import TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired(cmd=[], timeout=600)

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is False
        assert "timed out" in result["summary"]["error"]

    @patch('subprocess.run')
    def test_masscan_not_found(self, mock_subprocess, module, temp_dir):
        """Test handling when masscan binary is not found."""
        mock_subprocess.side_effect = FileNotFoundError()

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is False
        assert "masscan binary not found" in result["summary"]["error"]

    def test_parse_masscan_output_missing_file(self, module, temp_dir):
        """Test parsing when output file doesn't exist."""
        results_file = temp_dir / "missing.json"
        parsed = module._parse_masscan_output(results_file)

        assert parsed == []

    def test_parse_masscan_output_valid_json(self, module, temp_dir):
        """Test parsing valid JSON output."""
        results_file = temp_dir / "results.json"
        test_data = [{"ip": "1.2.3.4", "ports": [22, 80]}]

        with open(results_file, 'w') as f:
            json.dump(test_data, f)

        parsed = module._parse_masscan_output(results_file)

        assert parsed == test_data