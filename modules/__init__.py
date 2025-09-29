"""
ReconDragon Module Loader

Dynamically discovers and loads modules from the modules directory.
"""

import importlib
import inspect
import os
import logging
from typing import Dict, List, Type
from base import BaseModule

logger = logging.getLogger(__name__)


class ModuleLoader:
    """Handles discovery and loading of ReconDragon modules"""

    def __init__(self, modules_dir: str = None):
        if modules_dir is None:
            # Default to the directory containing this __init__.py
            modules_dir = os.path.dirname(os.path.abspath(__file__))
        self.modules_dir = modules_dir
        self._modules: Dict[str, Type[BaseModule]] = {}

    def discover_modules(self) -> Dict[str, Type[BaseModule]]:
        """
        Discover and load all valid modules from the modules directory.

        Returns:
            Dictionary mapping module names to module classes
        """
        self._modules.clear()

        # Find all Python files in modules directory
        for filename in os.listdir(self.modules_dir):
            if filename.endswith('_module.py') and filename != '__init__.py':
                module_name = filename[:-3]  # Remove .py extension
                try:
                    self._load_module(module_name)
                except Exception as e:
                    logger.warning(f"Failed to load module {module_name}: {e}")
                    continue

        return self._modules.copy()

    def _load_module(self, module_name: str):
        """Load a single module safely"""
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(
                module_name,
                os.path.join(self.modules_dir, f"{module_name}.py")
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec for {module_name}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find classes that inherit from BaseModule
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BaseModule) and
                    obj != BaseModule):
                    # Instantiate to check if it's valid
                    try:
                        instance = obj()
                        self._modules[instance.name] = obj
                        logger.info(f"Loaded module: {instance.name} v{instance.version}")
                        break  # Only take the first valid class per file
                    except Exception as e:
                        logger.warning(f"Could not instantiate {name}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error loading module {module_name}: {e}")
            raise

    def get_module(self, name: str) -> Type[BaseModule]:
        """Get a module class by name"""
        return self._modules.get(name)

    def list_modules(self) -> List[str]:
        """List all loaded module names"""
        return list(self._modules.keys())

    def get_all_modules(self) -> Dict[str, Type[BaseModule]]:
        """Get all loaded modules"""
        return self._modules.copy()


# Global loader instance
loader = ModuleLoader()

# Auto-discover modules on import
loader.discover_modules()