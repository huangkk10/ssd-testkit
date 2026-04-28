"""
Diskercise Configuration Management

This module provides configuration management and validation for Diskercise.
"""

import copy
from typing import Dict, Any

from .exceptions import DiskerciseConfigError


class DiskerciseConfig:
    """
    Configuration manager for Diskercise parameters.

    Example:
        >>> config = DiskerciseConfig.get_default_config()
        >>> print(config['test_duration_minutes'])
        15
        >>> DiskerciseConfig.validate_config({'thread_count': 4})
        True
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # Executable path
        'exe_path': 'C:\\tools\\Diskercise\\Diskercise.exe',

        # Logging
        'log_path': './testlog/diskercise',

        # Test mode
        'mode': 1,

        # GUI parameters
        'thread_count': 1,
        'file_size_mb': 0,
        'access_size_kb': 0,
        'read_ratio': 0,
        'write_ratio': 0,
        'data_type': 0,
        'buffered_io': True,

        # Advance Settings
        'adv_write_signatures': True,
        'adv_verify_immediate': True,
        'adv_pause_all_asap': True,
        'adv_pulse_com1': True,

        # Test duration
        'test_duration_minutes': 15,

        # Execution control
        'check_interval_seconds': 5.0,
        'window_wait_timeout': 30,
        'ui_retry_max': 3,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, type] = {
        'exe_path': str,
        'log_path': str,
        'mode': int,
        'thread_count': int,
        'file_size_mb': int,
        'access_size_kb': int,
        'read_ratio': int,
        'write_ratio': int,
        'data_type': int,
        'buffered_io': bool,
        'adv_write_signatures': bool,
        'adv_verify_immediate': bool,
        'adv_pause_all_asap': bool,
        'adv_pulse_com1': bool,
        'test_duration_minutes': int,
        'check_interval_seconds': (int, float),
        'window_wait_timeout': int,
        'ui_retry_max': int,
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
            DiskerciseConfigError: If any parameter is invalid.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise DiskerciseConfigError(f"Unknown config parameter: '{key}'")
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise DiskerciseConfigError(
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
            DiskerciseConfigError: If any override key is invalid.
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
