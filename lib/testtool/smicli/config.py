"""
SmiCli Configuration Management

This module provides configuration management and validation for SmiCli.
"""

import copy
from typing import Dict, Any

from .exceptions import SmiCliConfigError


class SmiCliConfig:
    """
    Configuration manager for SmiCli parameters.

    Example:
        >>> config = SmiCliConfig.get_default_config()
        >>> print(config['timeout_seconds'])
        60
        >>> SmiCliConfig.validate_config({'timeout_seconds': 30})
        True
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # Executable location — empty means auto-resolve via env vars at runtime
        'smicli_path': '',

        # Output file written by SmiCli2.exe --info
        'output_file': '',

        # Working directory for subprocess; empty means os.getcwd() at runtime
        'work_dir': '',

        # Subprocess timeout
        'timeout_seconds': 60,

        # Seconds to wait for SmiCli2.exe to flush the output file after exit
        'post_run_wait_seconds': 2,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, type] = {
        'smicli_path':            str,
        'output_file':            str,
        'work_dir':               str,
        'timeout_seconds':        (int, float),
        'post_run_wait_seconds':  (int, float),
    }

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Return a deep copy of the default configuration."""
        return copy.deepcopy(cls.DEFAULT_CONFIG)

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration parameter names and value types.

        Args:
            config: Dictionary of configuration parameters to validate.

        Returns:
            True if all parameters are valid.

        Raises:
            SmiCliConfigError: If an unknown key or wrong type is found.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise SmiCliConfigError(
                    f"Unknown config parameter: '{key}'. "
                    f"Valid parameters: {sorted(cls.VALID_PARAMS)}"
                )
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise SmiCliConfigError(
                    f"Config parameter '{key}' expects type {expected_type}, "
                    f"got {type(value).__name__}"
                )
        return True

    @classmethod
    def merge_config(cls, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge override values into a base config, returning a new dict.

        Args:
            base:      Base configuration dictionary.
            overrides: Values to override in the base.

        Returns:
            New merged configuration dictionary.
        """
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
