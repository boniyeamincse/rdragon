"""
Tests for NucleiModule

This module tests the NucleiModule functionality using pytest.
Mocks subprocess for nuclei execution and tests fallback behavior.
"""

import pytest
import tempfile
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from modules.nuclei_module import NucleiModule


@pytest.fixture
def nuclei_module():
    """Fixture for NucleiModule instance."""
    return NucleiModule()


@pytest.fixture
def temp_outdir():
    """Fixture for temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestNucleiModule:
    """Test cases for NucleiModule."""

    def test_module_properties(self, nuclei_module):
        """Test module name and version."""
        assert nuclei_module.name == "nuclei"
        assert nuclei_module.version == "2.0.0"

    def test_check_tool_availability(self, nuclei_module):
        """Test tool availability check."""
        with patch('shutil.which', return_value='/usr/bin/nuclei'):
            assert nuclei_module._check_tool_availability() is True

        with patch('shutil.which', return_value=None):
            assert nuclei_module._check_tool_availability() is False

    def test_generate_job_id(self, nuclei_module):
        """Test job ID generation."""
        targets = ["http://example.com", "https://test.com"]
        job_id = nuclei_module._generate_job_id(targets)
        assert isinstance(job_id, str)
        assert len(job_id) == 8

    def test_build_nuclei_commands_single_target(self, nuclei_module):
        """Test command building for single target."""
        targets = ["http://example.com"]
        commands = nuclei_module._build_nuclei_commands(targets, "/tmp/out", "/tmp/templates", "high,critical", 5)
        expected = [
            ["nuclei", "-oJ", "-severity", "high,critical", "-c", "5", "-t", "/tmp/templates", "-u", "http://example.com"]
        ]
        assert commands == expected

    def test_build_nuclei_commands_multiple_targets(self, nuclei_module):
        """Test command building for multiple targets."""
        targets = ["http://example.com", "https://test.com"]
        commands = nuclei_module._build_nuclei_commands(targets, "/tmp/out", None, "medium", 10)
        assert len(commands) == 1
        cmd = commands[0]
        assert cmd[:5] == ["nuclei", "-oJ", "-severity", "medium", "-c", "10"]
        assert "-l" in cmd

    def test_run_dry_mode(self, nuclei_module, temp_outdir):
        """Test dry-run mode."""
        result = nuclei_module.run("http://example.com", temp_outdir, execute=False)

        assert result["module"] == "nuclei"
        assert result["status"] == "dry-run"
        assert "commands" in result
        assert "job_id" in result
        assert result["targets"] == ["http://example.com"]

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_run_execute_mode_success(self, mock_run, mock_which, nuclei_module, temp_outdir):
        """Test execute mode with successful nuclei run."""
        mock_which.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Create mock nuclei output
        job_id = nuclei_module._generate_job_id(["http://example.com"])
        output_file = Path(temp_outdir) / f"nuclei_{job_id}.json"
        mock_findings = [
            {"template": "test", "info": {"severity": "high", "name": "Test Vuln"}},
            {"template": "test2", "info": {"severity": "critical", "name": "Critical Vuln"}}
        ]
        with open(output_file, 'w') as f:
            for finding in mock_findings:
                json.dump(finding, f)
                f.write('\n')

        result = nuclei_module.run("http://example.com", temp_outdir, execute=True)

        assert result["status"] == "completed"
        assert result["total_findings"] == 2
        assert result["counts"]["high"] == 1
        assert result["counts"]["critical"] == 1
        assert str(output_file) in result["artifacts"]

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_run_execute_mode_failure(self, mock_run, mock_which, nuclei_module, temp_outdir):
        """Test execute mode with nuclei failure."""
        mock_which.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Scan failed"
        mock_run.return_value = mock_result

        result = nuclei_module.run("http://example.com", temp_outdir, execute=True)

        assert result["status"] == "failed"
        assert result["total_findings"] == 0

    @patch('shutil.which')
    def test_run_execute_mode_fallback(self, mock_which, nuclei_module, temp_outdir):
        """Test fallback when nuclei not available."""
        mock_which.return_value = None

        # Create mock templates index
        index_file = Path(temp_outdir) / "templates_index.json"
        mock_templates = {
            "templates": [
                {
                    "id": "test-template",
                    "info": {"severity": "high", "name": "Test Vuln"},
                    "keywords": ["vulnerable"]
                }
            ]
        }
        with open(index_file, 'w') as f:
            json.dump(mock_templates, f)

        # Set index path
        nuclei_module.templates_index_path = str(index_file)

        result = nuclei_module.run("http://vulnerable.example.com", temp_outdir, execute=True, templates_path=str(index_file))

        assert result["status"] == "fallback"
        assert result["total_findings"] == 1
        assert result["findings"]["high"]["count"] == 1

    def test_parse_nuclei_output(self, nuclei_module, temp_outdir):
        """Test parsing nuclei JSON output."""
        output_file = Path(temp_outdir) / "test.json"
        mock_data = [
            {"template": "test", "info": {"severity": "high"}},
            {"template": "test2", "info": {"severity": "low"}}
        ]
        with open(output_file, 'w') as f:
            for item in mock_data:
                json.dump(item, f)
                f.write('\n')

        parsed = nuclei_module._parse_nuclei_output(output_file)
        assert len(parsed) == 2
        assert parsed[0]["info"]["severity"] == "high"

    def test_prioritize_findings(self, nuclei_module):
        """Test prioritizing findings by severity."""
        findings = [
            {"template": "high1", "info": {"severity": "high"}},
            {"template": "critical1", "info": {"severity": "critical"}},
            {"template": "high2", "info": {"severity": "high"}},
            {"template": "low1", "info": {"severity": "low"}},
        ]

        prioritized = nuclei_module._prioritize_findings(findings)

        assert prioritized["critical"]["count"] == 1
        assert prioritized["high"]["count"] == 2
        assert prioritized["low"]["count"] == 1
        assert len(prioritized["high"]["sample_findings"]) == 2

    def test_run_multiple_targets(self, nuclei_module, temp_outdir):
        """Test running against multiple targets."""
        targets = ["http://example.com", "https://test.com"]

        result = nuclei_module.run(targets, temp_outdir, execute=False)

        assert result["targets"] == targets
        assert "job_id" in result