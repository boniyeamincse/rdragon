"""
Unit tests for the ReconDragon module loader
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from modules import ModuleLoader
from base import BaseModule


class MockModule(BaseModule):
    """Mock module for testing"""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, target: str, outdir: str) -> dict:
        return {"module": "mock", "target": target}


class MockInvalidModule:
    """Invalid module that doesn't inherit from BaseModule"""
    pass


@pytest.fixture
def temp_modules_dir():
    """Create a temporary directory for testing modules"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def loader(temp_modules_dir):
    """Create a ModuleLoader instance with temp directory"""
    return ModuleLoader(temp_modules_dir)


def create_test_module_file(dir_path: str, filename: str, content: str):
    """Helper to create a test module file"""
    filepath = os.path.join(dir_path, filename)
    with open(filepath, 'w') as f:
        f.write(content)


def test_loader_initialization(loader):
    """Test ModuleLoader initialization"""
    assert loader.modules_dir.endswith('modules')
    assert loader._modules == {}


def test_discover_modules_empty_directory(loader):
    """Test discovering modules in empty directory"""
    modules = loader.discover_modules()
    assert modules == {}


def test_discover_valid_module(loader, temp_modules_dir):
    """Test discovering a valid module"""
    # Create a valid module file
    content = '''
from base import BaseModule

class TestModule(BaseModule):
    @property
    def name(self):
        return "test"

    @property
    def version(self):
        return "1.0.0"

    def run(self, target, outdir):
        return {"module": "test", "target": target}
'''
    create_test_module_file(temp_modules_dir, "test_module.py", content)

    # Update loader to use temp dir
    loader.modules_dir = temp_modules_dir
    modules = loader.discover_modules()

    assert "test" in modules
    assert issubclass(modules["test"], BaseModule)


def test_discover_invalid_module(loader, temp_modules_dir):
    """Test discovering an invalid module (doesn't inherit from BaseModule)"""
    content = '''
class InvalidModule:
    pass
'''
    create_test_module_file(temp_modules_dir, "invalid_module.py", content)

    loader.modules_dir = temp_modules_dir
    modules = loader.discover_modules()

    assert modules == {}  # Should not load invalid modules


def test_discover_module_with_import_error(loader, temp_modules_dir):
    """Test discovering a module with import errors"""
    content = '''
import nonexistent_module
from base import BaseModule

class ErrorModule(BaseModule):
    @property
    def name(self):
        return "error"

    @property
    def version(self):
        return "1.0.0"

    def run(self, target, outdir):
        return {"module": "error"}
'''
    create_test_module_file(temp_modules_dir, "error_module.py", content)

    loader.modules_dir = temp_modules_dir
    modules = loader.discover_modules()

    assert modules == {}  # Should not load modules with import errors


def test_get_module(loader):
    """Test getting a module by name"""
    loader._modules = {"mock": MockModule}
    module = loader.get_module("mock")
    assert module == MockModule

    module = loader.get_module("nonexistent")
    assert module is None


def test_list_modules(loader):
    """Test listing module names"""
    loader._modules = {"mock": MockModule, "test": MockModule}
    modules_list = loader.list_modules()
    assert set(modules_list) == {"mock", "test"}


def test_get_all_modules(loader):
    """Test getting all modules"""
    loader._modules = {"mock": MockModule}
    all_modules = loader.get_all_modules()
    assert all_modules == {"mock": MockModule}
    assert all_modules is not loader._modules  # Should return a copy


@patch('importlib.util.spec_from_file_location')
@patch('importlib.util.module_from_spec')
def test_load_module_spec_failure(mock_module_from_spec, mock_spec_from_file, loader):
    """Test handling of failed module spec loading"""
    mock_spec_from_file.return_value = None

    with pytest.raises(ImportError):
        loader._load_module("test_module")


@patch('importlib.util.spec_from_file_location')
@patch('importlib.util.module_from_spec')
def test_load_module_exec_failure(mock_module_from_spec, mock_spec_from_file, loader):
    """Test handling of module execution failure"""
    mock_spec = MagicMock()
    mock_spec_from_file.return_value = mock_spec
    mock_spec.loader = MagicMock()
    mock_spec.loader.exec_module.side_effect = Exception("Exec failed")

    with pytest.raises(Exception):
        loader._load_module("test_module")


def test_module_instantiation_failure(loader, temp_modules_dir):
    """Test handling of module instantiation failure"""
    content = '''
from base import BaseModule

class BrokenModule(BaseModule):
    @property
    def name(self):
        return "broken"

    @property
    def version(self):
        return "1.0.0"

    def run(self, target, outdir):
        return {}

    def __init__(self):
        raise ValueError("Instantiation failed")
'''
    create_test_module_file(temp_modules_dir, "broken_module.py", content)

    loader.modules_dir = temp_modules_dir
    modules = loader.discover_modules()

    assert modules == {}  # Should not load modules that can't be instantiated