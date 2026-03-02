"""
OsReboot Configuration Management

Provides default configuration, type validation, and config merging
for the OsReboot controller.  All reboot parameters are defined here
so that callers can either accept the defaults or pass partial overrides.

Example::

    >>> config = OsRebootConfig.get_default_config()
    >>> print(config['delay_seconds'])
    10
    >>> OsRebootConfig.validate_config({'reboot_count': 3, 'delay_seconds': 5})
    True
    >>> merged = OsRebootConfig.merge_config(config, {'reboot_count': 2})
    >>> print(merged['reboot_count'])
    2
"""

import copy
from typing import Dict, Any

from .exceptions import OsRebootConfigError


class OsRebootConfig:
    """
    Configuration manager for OsReboot parameters.

    Handles default values, type validation, and config merging.

    Attributes:
        DEFAULT_CONFIG: Default parameter values used when no overrides are given.
        VALID_PARAMS:   Set of all legal parameter names.
        PARAM_TYPES:    Mapping from parameter name to expected Python type(s).
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # --- Reboot timing ---
        # Number of seconds passed to ``shutdown /r /t <delay_seconds>``
        'delay_seconds': 10,

        # --- Cycle control ---
        # Total number of reboot cycles to perform
        'reboot_count': 1,

        # --- State persistence ---
        # Path to the JSON state file used to track cycle count across reboots
        'state_file': 'reboot_state.json',

        # --- Error handling ---
        # When True, stop the sequence immediately if shutdown.exe returns
        # a non-zero exit code; when False, log the error and continue.
        'abort_on_fail': True,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, Any] = {
        'delay_seconds':  int,
        'reboot_count':   int,
        'state_file':     str,
        'abort_on_fail':  bool,
    }

    # ------------------------------------------------------------------ #
    # Core class-methods                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Return a deep copy of the default configuration."""
        return copy.deepcopy(cls.DEFAULT_CONFIG)

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration parameters.

        Checks:
        - No unknown keys.
        - Each value matches the declared type.
        - ``delay_seconds`` >= 0 (0 = immediate).
        - ``reboot_count`` >= 1.

        Args:
            config: Configuration dict to validate (may be partial).

        Returns:
            ``True`` if all values are valid.

        Raises:
            OsRebootConfigError: If any parameter is invalid.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise OsRebootConfigError(
                    f"Unknown config parameter: '{key}'"
                )
            expected = cls.PARAM_TYPES.get(key)
            if expected is not None and not isinstance(value, expected):
                raise OsRebootConfigError(
                    f"Parameter '{key}' must be {expected.__name__}, "
                    f"got {type(value).__name__}"
                )

        # --- Semantic validations ---
        if 'delay_seconds' in config and config['delay_seconds'] < 0:
            raise OsRebootConfigError(
                f"'delay_seconds' must be >= 0, got {config['delay_seconds']}"
            )

        if 'reboot_count' in config and config['reboot_count'] < 1:
            raise OsRebootConfigError(
                f"'reboot_count' must be >= 1, got {config['reboot_count']}"
            )

        return True

    @classmethod
    def merge_config(
        cls,
        base: Dict[str, Any],
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge override values into a base config dict.

        Args:
            base:      Base configuration dict.
            overrides: Values to override (validated before merge).

        Returns:
            New merged configuration dict (``base`` is not mutated).

        Raises:
            OsRebootConfigError: If any override key/value is invalid.
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged
