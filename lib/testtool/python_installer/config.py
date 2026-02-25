"""
PythonInstaller Configuration Management

This module provides configuration management and validation for the Python
installation/uninstallation workflow. Supports specifying the target Python version,
install directory, and installer download or path.
"""

import copy
from typing import Dict, Any, Tuple

from .exceptions import PythonInstallerConfigError

# Officially supported Python version range
SUPPORTED_MAJOR_MINOR: Tuple[int, int] = (3, 6)   # minimum major.minor


class PythonInstallerConfig:
    """
    Configuration manager for PythonInstaller parameters.

    Example:
        >>> config = PythonInstallerConfig.get_default_config()
        >>> PythonInstallerConfig.validate_config({'version': '3.11'})
        True
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # Target Python version (e.g. "3.11", "3.11.8")
        'version': '3.11',
        # Architecture: "amd64" or "win32"
        'architecture': 'amd64',
        # Installation directory.  Empty string = use Windows default.
        'install_path': '',
        # Whether to add Python to PATH / associate file extensions
        'add_to_path': True,
        # Pre-downloaded installer .exe path.  If empty, auto-download.
        'installer_path': '',
        # Directory to store downloaded installer (when installer_path is empty)
        'download_dir': './testlog/python_installer',
        # Whether to uninstall Python after the test
        'uninstall_after_test': False,
        # Seconds to wait for install / uninstall to complete
        'timeout_seconds': 300,
        # Polling interval while waiting for process
        'check_interval_seconds': 2.0,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, Any] = {
        'version': str,
        'architecture': str,
        'install_path': str,
        'add_to_path': bool,
        'installer_path': str,
        'download_dir': str,
        'uninstall_after_test': bool,
        'timeout_seconds': int,
        'check_interval_seconds': (int, float),
    }

    VALID_ARCHITECTURES = ('amd64', 'win32')

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Return a deep copy of the default configuration."""
        return copy.deepcopy(cls.DEFAULT_CONFIG)

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration parameters.

        Args:
            config: Configuration dict to validate.

        Returns:
            True if valid.

        Raises:
            PythonInstallerConfigError: If any parameter is invalid.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise PythonInstallerConfigError(f"Unknown config parameter: '{key}'")
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise PythonInstallerConfigError(
                    f"Parameter '{key}' must be {expected_type}, "
                    f"got {type(value).__name__}"
                )

        # Cross-field validation
        if 'version' in config:
            cls._validate_version(config['version'])

        if 'architecture' in config:
            arch = config['architecture']
            if arch not in cls.VALID_ARCHITECTURES:
                raise PythonInstallerConfigError(
                    f"architecture must be one of {cls.VALID_ARCHITECTURES}, got '{arch}'"
                )

        if 'timeout_seconds' in config and config['timeout_seconds'] <= 0:
            raise PythonInstallerConfigError("timeout_seconds must be > 0")

        if 'check_interval_seconds' in config and config['check_interval_seconds'] <= 0:
            raise PythonInstallerConfigError("check_interval_seconds must be > 0")

        return True

    @classmethod
    def _validate_version(cls, version: str) -> None:
        """
        Validate version string format and supported range.

        Accepts: "3.11", "3.11.8", "3.12.0"
        Raises:  PythonInstallerConfigError on invalid/unsupported version.
        """
        parts = version.split('.')
        if len(parts) < 2 or len(parts) > 3:
            raise PythonInstallerConfigError(
                f"version must be 'MAJOR.MINOR' or 'MAJOR.MINOR.PATCH', got '{version}'"
            )
        try:
            major = int(parts[0])
            minor = int(parts[1])
            if len(parts) == 3:
                int(parts[2])
        except ValueError:
            raise PythonInstallerConfigError(
                f"version components must be integers, got '{version}'"
            )

        min_major, min_minor = SUPPORTED_MAJOR_MINOR
        if (major, minor) < (min_major, min_minor):
            raise PythonInstallerConfigError(
                f"version '{version}' is below minimum supported "
                f"{min_major}.{min_minor}"
            )
        if major != 3:
            raise PythonInstallerConfigError(
                f"Only Python 3.x is supported, got '{version}'"
            )

    @classmethod
    def merge_config(cls, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge override values into base config.

        Args:
            base:      Base configuration dict.
            overrides: Values to override.

        Returns:
            Merged configuration dict.

        Raises:
            PythonInstallerConfigError: If overrides contain invalid params.
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
