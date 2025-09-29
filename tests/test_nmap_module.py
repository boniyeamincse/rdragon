"""
Unit tests for NmapModule.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from modules.nmap_module import NmapModule


class TestNmapModule:
    @pytest.fixture
    def module(self):
        return NmapModule()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_name_property(self, module):
        assert module.name == "nmap"

    def test_version_property(self, module):
        assert module.version == "1.0.0"

    def test_dry_run_mode(self, module, temp_dir):
        """Test dry-run doesn't execute subprocess."""
        result = module.run("192.168.1.1", str(temp_dir), execute=False)

        assert result["module"] == "nmap"
        assert result["success"] is True
        assert "Dry-run" in str(result.get("summary", {}).get("error", ""))

    @patch('subprocess.run')
    def test_successful_scan(self, mock_subprocess, module, temp_dir):
        """Test successful nmap execution."""
        mock_process = MagicMock()
        mock_process.stdout = ""
        mock_subprocess.return_value = mock_process

        # Mock XML file
        xml_file = temp_dir / "nmap_192_168_1_1.xml"
        xml_content = '''<?xml version="1.0"?>
<nmaprun>
<host><status state="up"/><address addr="192.168.1.1"/>
<ports><port portid="80" protocol="tcp"><state state="open"/><service name="http"/></port></ports>
</host>
</nmaprun>'''
        with open(xml_file, 'w') as f:
            f.write(xml_content)

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is True
        assert result["summary"]["open_ports"] == 1
        assert str(xml_file) in result["artifacts"]

    @patch('subprocess.run')
    def test_scan_failure(self, mock_subprocess, module, temp_dir):
        """Test handling of scan failure."""
        from subprocess import CalledProcessError
        mock_subprocess.side_effect = CalledProcessError(cmd=[], returncode=1, stderr="Scan failed")

        result = module.run("192.168.1.1", str(temp_dir), execute=True)

        assert result["success"] is False
        assert "Nmap failed" in result["summary"]["error"]