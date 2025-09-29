"""
ReconDragon Base Classes and Interfaces
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseModule(ABC):
    """
    Abstract base class for all ReconDragon modules.

    Modules should implement this class to provide reconnaissance functionality.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Module name identifier"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Module version"""
        pass

    @abstractmethod
    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute the module's reconnaissance functionality.

        Args:
            target: The target to scan (IP or domain)
            outdir: Output directory for results
            execute: Whether to actually run external commands (default: False for dry-run)
            **kwargs: Additional module-specific parameters

        Returns:
            Dict containing scan results with standardized structure
        """
        pass