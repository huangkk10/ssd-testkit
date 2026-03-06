"""
PwrTest Configuration Management

This module provides configuration management and validation for PwrTest.
It supports multi-OS / multi-version executable path resolution so that
the correct pwrtest.exe is selected automatically based on the running OS.
"""

import copy
import warnings
from enum import Enum
from typing import Dict, Any, List
from pathlib import Path

from .exceptions import PwrTestConfigError


# Known pwrtest OS/version directory names discovered from SmiWinTools layout.
# Entries are used for optional validation warnings — unknown values are allowed
# so that newly released OS versions keep working without code changes.
KNOWN_OS_VERSIONS: Dict[str, List[str]] = {
    "win7":  [],
    "win10": ["1709", "1803", "1809", "1903", "1909", "2004"],
    "win11": ["21H2", "22H2", "24H2", "25H2"],
}

_VALID_OS_NAMES = set(KNOWN_OS_VERSIONS.keys())


class PwrTestScenario(Enum):
    """
    pwrtest.exe sleep scenario selection.

    Attributes:
        CS:    Connected Standby / Modern Standby (S0ix) — for AoAc systems
               (most modern laptops / tablets with ``AoAc=1``).
        SLEEP: Traditional S3 sleep — for legacy systems that expose S3.

    Example::

        from lib.testtool.pwrtest import PwrTestController, PwrTestScenario

        ctrl = PwrTestController(
            scenario=PwrTestScenario.CS,
            ...
        )
    """
    CS    = 'cs'
    SLEEP = 'sleep'


class PwrTestConfig:
    """
    Configuration manager for PwrTest parameters.

    Handles default values, type validation, config merging, and
    dynamic resolution of the pwrtest.exe path from os_name + os_version.

    Example:
        >>> config = PwrTestConfig.get_default_config()
        >>> print(config['cycle_count'])
        1
        >>> PwrTestConfig.validate_config({'cycle_count': 3})
        True
        >>> exe = PwrTestConfig.resolve_executable_path(config)
        >>> print(exe.name)
        pwrtest.exe
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        # --- Executable path ---
        # When non-empty this path is used directly; otherwise os_name+os_version
        # are combined with pwrtest_base_dir to produce the final path.
        'executable_path': '',

        # Root directory of the pwrtest sub-tree inside SmiWinTools
        'pwrtest_base_dir': (
            './tests/unit/lib/testtool/bin/SmiWinTools/bin/x64/pwrtest'
        ),

        # --- OS version selection ---
        'os_name':    'win11',   # win7 | win10 | win11
        'os_version': '25H2',    # directory under os_name; e.g. 25H2, 2004, 22H2

        # --- Scenario ---
        # PwrTestScenario.CS    — Connected Standby / Modern Standby (S0ix)
        # PwrTestScenario.SLEEP — Traditional S3 (legacy systems)
        'scenario': PwrTestScenario.CS,

        # --- Sleep test parameters ---
        'cycle_count':        1,    # /c — number of sleep cycles
        'delay_seconds':      10,   # /d — seconds before entering sleep
        'wake_after_seconds': 30,   # /p — seconds until OS wakes up

        # --- Output / logging ---
        'log_path':   './testlog/PwrTestLog',
        'log_prefix': '',

        # --- Execution control ---
        'timeout_seconds':        300,   # must be > cycle_count*(delay+wake)+margin
        'check_interval_seconds': 2.0,
    }

    VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, type] = {
        'executable_path':        str,
        'pwrtest_base_dir':       str,
        'os_name':                str,
        'os_version':             str,
        'scenario':               (str, PwrTestScenario),
        'cycle_count':            int,
        'delay_seconds':          int,
        'wake_after_seconds':     int,
        'log_path':               str,
        'log_prefix':             str,
        'timeout_seconds':        int,
        'check_interval_seconds': (int, float),
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
        - ``os_name`` is one of the known values (``win7``, ``win10``, ``win11``).
        - Positive-integer constraints on ``cycle_count``, ``delay_seconds``,
          ``wake_after_seconds``.
        - Warns (does not raise) when ``timeout_seconds`` may be too short.

        Args:
            config: Configuration dict to validate.

        Returns:
            ``True`` if valid.

        Raises:
            PwrTestConfigError: If any parameter is invalid.
        """
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise PwrTestConfigError(
                    f"Unknown config parameter: '{key}'"
                )
            expected_type = cls.PARAM_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                raise PwrTestConfigError(
                    f"Parameter '{key}' must be {expected_type}, "
                    f"got {type(value).__name__}"
                )

        # --- Semantic validations ---
        if 'os_name' in config and config['os_name'] not in _VALID_OS_NAMES:
            raise PwrTestConfigError(
                f"'os_name' must be one of {sorted(_VALID_OS_NAMES)}, "
                f"got '{config['os_name']}'"
            )

        for pos_int_key in ('cycle_count', 'delay_seconds', 'wake_after_seconds'):
            if pos_int_key in config and config[pos_int_key] <= 0:
                raise PwrTestConfigError(
                    f"'{pos_int_key}' must be a positive integer, "
                    f"got {config[pos_int_key]}"
                )

        # --- Advisory warning on timeout ---
        # Build a merged view to check timeout against cycle params
        merged = {**cls.DEFAULT_CONFIG, **config}
        min_expected = (
            merged['cycle_count']
            * (merged['delay_seconds'] + merged['wake_after_seconds'])
        )
        if merged['timeout_seconds'] <= min_expected:
            warnings.warn(
                f"'timeout_seconds' ({merged['timeout_seconds']}s) may be too short. "
                f"Estimated minimum: {min_expected}s "
                f"(cycle_count={merged['cycle_count']} × "
                f"(delay={merged['delay_seconds']} + wake={merged['wake_after_seconds']})). "
                "Consider adding a safety margin.",
                UserWarning,
                stacklevel=3,
            )

        # --- Advisory warning for unknown os_version ---
        if 'os_version' in config:
            os_name = config.get('os_name', cls.DEFAULT_CONFIG['os_name'])
            known = KNOWN_OS_VERSIONS.get(os_name, [])
            if known and config['os_version'] not in known:
                warnings.warn(
                    f"'os_version' '{config['os_version']}' is not in the known list "
                    f"for '{os_name}': {known}. "
                    "The path will still be constructed — validate manually.",
                    UserWarning,
                    stacklevel=3,
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
            New merged configuration dict (base is not mutated).

        Raises:
            PwrTestConfigError: If any override key/value is invalid.
        """
        cls.validate_config(overrides)
        merged = copy.deepcopy(base)
        merged.update(overrides)
        return merged

    # ------------------------------------------------------------------ #
    # Path resolution                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def resolve_executable_path(cls, config: Dict[str, Any]) -> Path:
        """
        Resolve the absolute path to ``pwrtest.exe``.

        Resolution order:
        1. If ``executable_path`` is non-empty, use it directly.
        2. Otherwise compose: ``pwrtest_base_dir / os_name / os_version / pwrtest.exe``.

        Args:
            config: A config dict (may be partial; unset keys fall back to
                    ``DEFAULT_CONFIG`` values).

        Returns:
            :class:`pathlib.Path` pointing to ``pwrtest.exe``.
        """
        exe_path = config.get(
            'executable_path', cls.DEFAULT_CONFIG['executable_path']
        )
        if exe_path:
            return Path(exe_path)

        base_dir = config.get(
            'pwrtest_base_dir', cls.DEFAULT_CONFIG['pwrtest_base_dir']
        )
        os_name = config.get('os_name', cls.DEFAULT_CONFIG['os_name'])
        os_version = config.get('os_version', cls.DEFAULT_CONFIG['os_version'])
        return Path(base_dir) / os_name / os_version / 'pwrtest.exe'

    @classmethod
    def get_supported_os_versions(cls) -> Dict[str, List[str]]:
        """
        Return the built-in map of known OS names to their version directories.

        Returns:
            A copy of :data:`KNOWN_OS_VERSIONS`.
        """
        return copy.deepcopy(KNOWN_OS_VERSIONS)
