"""
Unit tests for NucleiModule.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from modules.nuclei_module import NucleiModule


class TestNucleiModule:
    @pytest.fixture
    def module(self):
        return NucleiModule()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_name_property(self, module):
        assert module.name == "nuclei"

    def test_version_property(self, module):
        assert module.version == "1.0.0"

    def test_dry_run_mode(self, module, temp_dir):
        """Test dry-run doesn't execute subprocess."""
        result = module.run("http://example.com", str(temp_dir), execute=False)

        assert result["module"] == "nuclei"
        assert result["success"] is True

    @patch('subprocess.run')
    def test_successful_scan(self, mock_subprocess, module, temp_dir):
        """Test successful nuclei execution."""
        mock_process = MagicMock()
        mock_process.stdout = ""
        mock_subprocess.return_value = mock_process

        # Create mock JSON output file
        results_file = temp_dir / "nuclei_results.json"
        mock_data = [
            {"template": "test", "info": {"severity": "high"}},
            {"template": "test2", "info": {"severity": "medium"}}
        ]
        with open(results_file, 'w') as f:
            for item in mock_data:
                json.dump(item, f)
                f.write('\n')

        result = module.run("http://example.com", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["vulnerabilities_found"] == 2
        assert result["summary"]["severity_breakdown"]["high"] == 1
        assert str(results_file) in result["artifacts"]

    @patch('subprocess.run')
    def test_scan_failure(self, mock_subprocess, module, temp_dir):
        """Test handling of scan failure."""
        from subprocess import CalledProcessError
        mock_subprocess.side_effect = CalledProcessError(cmd=[], returncode=1, stderr="Scan failed")

        result = module.run("http://example.com", str(temp_dir), execute=True)

        assert result["success"] is False
        assert "Nuclei failed" in result["summary"]["error"]