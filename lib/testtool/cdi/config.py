"""
CDI (CrystalDiskInfo) Configuration Management

This module provides configuration management and validation for CDI.
"""

import copy
from typing import Dict, Any

from .exceptions import CDIConfigError


class CDIConfig:
    """
    Configuration manager for CDI (CrystalDiskInfo) parameters.

    Example:
        >>> config = CDIConfig.get_default_config()
        >>> CDIConfig.validate_config({'executable_path': './bin/CrystalDiskInfo/DiskInfo64.exe'})
        True
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # Executable location
        'executable_path': './bin/CrystalDiskInfo/DiskInfo64.exe',
        # Log output directory
        'log_path': './testlog',
        # Filename prefix applied to all output files
        'log_prefix': '',
        # Drive letter to capture screenshot for (e.g. 'C:'); empty = all drives
        'screenshot_drive_letter': '',
        # Output filenames
        'diskinfo_txt_name': 'DiskInfo.txt',
        'diskinfo_json_name': 'DiskInfo.json',
        'diskinfo_png_name': '',
        # pywinauto window identifiers
        'window_title': ' CrystalDiskInfo ',
        'window_class': '#32770',
        # Save-dialog timeouts and retries
        'save_dialog_timeout': 20,
        'save_retry_max': 10,
        # Controller execution limits
        'timeout_seconds': 300,
        'check_interval_seconds': 2.0,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, type] = {
        'executable_path': str,
        'log_path': str,
        'log_prefix': str,
        'screenshot_drive_letter': str,
        'diskinfo_txt_name': str,
        'diskinfo_json_name': str,
        'diskinfo_png_name': str,
        'window_title': str,
        'window_class': str,
        'save_dialog_timeout': (int, float),
        'save_retry_max': int,
        'timeout_seconds': (int, float),
        'check_interval_seconds': (int, float),
    }

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
            CDIConfigError: If any parameter is invalid.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise CDIConfigError(f"Unknown config parameter: '{key}'")
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise CDIConfigError(
                    f"Parameter '{key}' must be {expected_type}, got {type(value).__name__}"
                )
        return True

    @classmethod
    def merge_config(cls, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge override values into base config.

        Args:
            base: Base configuration dict.
            overrides: Values to override.

        Returns:
            Merged configuration dict.

        Raises:
            CDIConfigError: If any override key is invalid.
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
