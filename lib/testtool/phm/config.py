"""
PHM (Powerhouse Mountain) Configuration Management

This module provides configuration management and validation for PHM.
"""

import copy
from typing import Dict, Any

from .exceptions import PHMConfigError


class PHMConfig:
    """
    Configuration manager for PHM parameters.

    This class provides:
    - Default configuration values
    - Configuration validation
    - Configuration merging

    Example:
        >>> config = PHMConfig.get_default_config()
        >>> print(config['cycle_count'])
        10
        >>> PHMConfig.validate_config({'cycle_count': 50})
        True
    """

    # Default configuration values
    DEFAULT_CONFIG: Dict[str, Any] = {
        # Installation paths
        'installer_path': '',
        'install_path': 'C:\\Program Files\\PowerhouseMountain',
        'executable_name': 'PowerhouseMountain.exe',

        # Web UI (PHM runs as a Node.js web server on localhost)
        'phm_host': 'localhost',
        'phm_port': 1337,
        'browser_headless': False,
        'browser_timeout': 30000,   # ms, Playwright page load timeout

        # Test parameters
        'cycle_count': 10,
        'test_duration_minutes': 60,
        'enable_modern_standby': True,
        'dut_id': '0',

        # Logging
        'log_path': './testlog/PHMLog',
        'log_prefix': '',
        'enable_screenshot': True,
        'screenshot_path': './testlog/PHMLog/screenshots',

        # Execution control
        'timeout': 3600,
        'check_interval_seconds': 5,
        'ui_retry_max': 60,
        'ui_retry_interval_seconds': 3,
    }

    # Valid parameter names
    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    # Type mapping for validation
    PARAM_TYPES: Dict[str, type] = {
        'installer_path': str,
        'install_path': str,
        'executable_name': str,
        'phm_host': str,
        'phm_port': int,
        'browser_headless': bool,
        'browser_timeout': int,
        'cycle_count': int,
        'test_duration_minutes': int,
        'enable_modern_standby': bool,
        'dut_id': str,
        'log_path': str,
        'log_prefix': str,
        'enable_screenshot': bool,
        'screenshot_path': str,
        'timeout': (int, float),
        'check_interval_seconds': (int, float),
        'ui_retry_max': int,
        'ui_retry_interval_seconds': (int, float),
    }

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Return a deep copy of the default configuration.

        Returns:
            Dict[str, Any]: Mutable copy of DEFAULT_CONFIG.

        Example:
            >>> config = PHMConfig.get_default_config()
            >>> config['cycle_count'] = 100
        """
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
            PHMConfigError: If any parameter is unknown or has wrong type.

        Example:
            >>> PHMConfig.validate_config({'cycle_count': 50})
            True
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise PHMConfigError(f"Unknown config parameter: '{key}'")
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise PHMConfigError(
                    f"Parameter '{key}' must be {expected_type}, "
                    f"got {type(value).__name__}"
                )
        return True

    @classmethod
    def merge_config(cls, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge override values into a base config.

        Args:
            base: Base configuration dict.
            overrides: Values to override (must pass validation).

        Returns:
            New merged configuration dict.

        Raises:
            PHMConfigError: If overrides contain invalid parameters.

        Example:
            >>> base = PHMConfig.get_default_config()
            >>> merged = PHMConfig.merge_config(base, {'cycle_count': 100})
            >>> merged['cycle_count']
            100
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
