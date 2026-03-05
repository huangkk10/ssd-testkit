"""
SleepStudy Configuration

Provides :data:`DEFAULT_CONFIG`, :class:`SleepStudyConfig`, and
:func:`merge_config` for the ``lib.testtool.sleepstudy`` package.
"""

from typing import Any, Dict

from .exceptions import SleepStudyConfigError

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # Path where powercfg /sleepstudy writes its HTML output.
    "output_path": "sleepstudy-report.html",
    # How long (seconds) to wait for powercfg to complete.
    "timeout": 60,
}

VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())


# ---------------------------------------------------------------------------
# Config class
# ---------------------------------------------------------------------------

class SleepStudyConfig:
    """
    Configuration container for :class:`~.controller.SleepStudyController`.

    Args:
        **kwargs: Override any key from :data:`DEFAULT_CONFIG`.

    Raises:
        :class:`~.exceptions.SleepStudyConfigError`: if an unknown key is
            supplied or a value fails type validation.

    Example:
        >>> cfg = SleepStudyConfig(output_path="C:/tmp/report.html", timeout=30)
        >>> cfg.output_path
        'C:/tmp/report.html'
    """

    def __init__(self, **kwargs: Any) -> None:
        config = merge_config(kwargs)
        self.output_path: str = config["output_path"]
        self.timeout: int = config["timeout"]

    def __repr__(self) -> str:
        return (
            f"SleepStudyConfig(output_path={self.output_path!r}, "
            f"timeout={self.timeout!r})"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def merge_config(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge *overrides* on top of :data:`DEFAULT_CONFIG` and validate.

    Args:
        overrides: Mapping of parameter names to values.

    Returns:
        Complete config dict with all keys populated.

    Raises:
        :class:`~.exceptions.SleepStudyConfigError`: on unknown keys or
            invalid values.
    """
    unknown = set(overrides) - VALID_PARAMS
    if unknown:
        raise SleepStudyConfigError(
            f"Unknown SleepStudy config parameter(s): {sorted(unknown)}"
        )

    config = {**DEFAULT_CONFIG, **overrides}
    _validate(config)
    return config


def _validate(config: Dict[str, Any]) -> None:
    if not isinstance(config["output_path"], str) or not config["output_path"]:
        raise SleepStudyConfigError(
            f"output_path must be a non-empty string, got {config['output_path']!r}"
        )
    if not isinstance(config["timeout"], (int, float)) or config["timeout"] <= 0:
        raise SleepStudyConfigError(
            f"timeout must be a positive number, got {config['timeout']!r}"
        )
