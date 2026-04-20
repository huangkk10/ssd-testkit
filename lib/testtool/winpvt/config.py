"""
WinPVT Configuration Management

Default configuration, validation and merging for WinPVTController.
"""

from typing import Any, Dict


class WinPVTConfig:
    """Configuration manager for WinPVT parameters."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        # Executable
        'exe_path': r'C:\Program Files\Hewlett-Packard\WinPVT 11.16.0\WinPVT.exe',
        # Output paths
        'result_path': './testlog/WinPVTResult',
        'screenshot_dir': './testlog/WinPVTScreenshots',
        # Test parameters
        'test_category': 'Standby',
        'stress_level': 'Critical',
        'timeout_minutes': 120,
        # Test plan (.pvt) file to load after startup dialogs are cleared
        'pvt_file': (
            r'C:\Program Files\Hewlett-Packard\WinPVT 11.16.0'
            r'\Test Plans\Power Management\Standby Critical Only.pvt'
        ),
        # Dialog handling
        'dialog_dismiss_timeout': 120,
        # Window wait
        'window_wait_timeout': 30,
    }

    VALID_PARAMS = set(DEFAULT_CONFIG.keys())

    PARAM_TYPES: Dict[str, Any] = {
        'exe_path': str,
        'result_path': str,
        'screenshot_dir': str,
        'test_category': str,
        'stress_level': str,
        'timeout_minutes': (int, float),
        'pvt_file': str,
        'dialog_dismiss_timeout': (int, float),
        'window_wait_timeout': (int, float),
    }

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return dict(cls.DEFAULT_CONFIG)

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        for key, value in config.items():
            if key not in cls.VALID_PARAMS:
                raise ValueError(f"Unknown WinPVT config param: {key!r}")
            expected = cls.PARAM_TYPES.get(key)
            if expected and not isinstance(value, expected):
                raise TypeError(
                    f"WinPVT config {key!r}: expected {expected}, got {type(value)}"
                )
        return True

    @classmethod
    def merge_config(cls, base: Dict[str, Any],
                     overrides: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        merged.update(overrides)
        return merged
