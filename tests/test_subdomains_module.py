"""
Tests for SubdomainsModule

This module tests the SubdomainsModule functionality using pytest.
"""

import pytest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path
from modules.subdomains_module import SubdomainsModule


@pytest.fixture
def subdomains_module():
    """Fixture for SubdomainsModule instance."""
    return SubdomainsModule()


@pytest.fixture
def temp_outdir():
    """Fixture for temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestSubdomainsModule:
    """Test cases for SubdomainsModule."""

    def test_module_properties(self, subdomains_module):
        """Test module name and version."""
        assert subdomains_module.name == "subdomains"
        assert subdomains_module.version == "1.0.0"

    def test_sanitize_target_valid(self, subdomains_module):
        """Test target sanitization with valid domain."""
        assert subdomains_module._sanitize_target("example.com") == "example.com"

    def test_sanitize_target_invalid(self, subdomains_module):
        """Test target sanitization with invalid domain."""
        with pytest.raises(ValueError):
            subdomains_module._sanitize_target("invalid")

    @patch('shutil.which')
    def test_get_available_tools(self, mock_which, subdomains_module):
        """Test tool availability detection."""
        mock_which.side_effect = lambda tool: tool in ["subfinder", "findomain"]
        available = subdomains_module._get_available_tools(["subfinder", "amass", "findomain"])
        assert available == ["subfinder", "findomain"]

    def test_build_command_subfinder(self, subdomains_module):
        """Test command building for subfinder."""
        cmd = subdomains_module._build_command("subfinder", "example.com", "/tmp/out.txt", 300)
        expected = ["subfinder", "-d", "example.com", "-o", "/tmp/out.txt", "-timeout", "300", "-silent"]
        assert cmd == expected

    def test_build_command_amass(self, subdomains_module):
        """Test command building for amass."""
        cmd = subdomains_module._build_command("amass", "example.com", "/tmp/out.txt", 300)
        expected = ["amass", "enum", "-d", "example.com", "-o", "/tmp/out.txt", "-timeout", "300"]
        assert cmd == expected

    def test_build_command_findomain(self, subdomains_module):
        """Test command building for findomain."""
        cmd = subdomains_module._build_command("findomain", "example.com", "/tmp/out.txt", 300)
        expected = ["findomain", "-t", "example.com", "-o", "/tmp/out.txt", "--quiet"]
        assert cmd == expected

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_run_dry_mode(self, mock_run, mock_which, subdomains_module, temp_outdir):
        """Test dry-run mode."""
        mock_which.return_value = True

        result = subdomains_module.run("example.com", temp_outdir, execute=False)

        assert result["module"] == "subdomains"
        assert result["target"] == "example.com"
        assert result["success"] is True
        assert "commands" in result["raw"]
        assert len(result["raw"]["commands"]) == 3
        # Ensure no actual execution
        mock_run.assert_not_called()

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_run_execute_mode_success(self, mock_run, mock_which, subdomains_module, temp_outdir):
        """Test execute mode with successful tool runs."""
        mock_which.side_effect = lambda tool: tool in ["subfinder", "findomain"]

        # Mock subprocess.run to simulate success and create output files
        def mock_subprocess_run(cmd, **kwargs):
            tool = cmd[0]
            output_file = cmd[cmd.index("-o") + 1] if "-o" in cmd else cmd[cmd.index("-t") + 2]
            Path(output_file).write_text(f"sub1.{tool}.com\nsub2.{tool}.com\n")
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        mock_run.side_effect = mock_subprocess_run

        result = subdomains_module.run("example.com", temp_outdir, execute=True, tools=["subfinder", "findomain"])

        assert result["success"] is True
        assert result["summary"]["total_subdomains"] > 0
        assert Path(temp_outdir, "subdomains.txt").exists()

        # Check merged file contains unique subdomains
        with open(Path(temp_outdir, "subdomains.txt")) as f:
            merged = f.read().strip().split("\n")
            assert len(merged) == 4  # 2 from each tool, all unique

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_run_execute_mode_failure(self, mock_run, mock_which, subdomains_module, temp_outdir):
        """Test execute mode with tool failures."""
        mock_which.return_value = True
        mock_run.side_effect = subprocess.CalledProcessError(1, "command", stderr="Error")

        result = subdomains_module.run("example.com", temp_outdir, execute=True)

        assert result["success"] is False
        assert result["summary"]["total_subdomains"] == 0