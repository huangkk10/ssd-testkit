"""
OsConfig — profile_loader

Load an :class:`~lib.testtool.osconfig.config.OsConfigProfile` from a YAML
file instead of hard-coding individual ``cfg.get(...)`` calls inside the test.

Usage::

    from lib.testtool.osconfig.profile_loader import load_profile

    profile = load_profile(Path(__file__).parent / "Config" / "osconfig.yaml")
    controller = OsConfigController(profile=profile, state_manager=state_mgr)
    controller.apply_all()

YAML format — only list fields you want to set to ``True`` (or a non-default
value).  Unknown keys raise :class:`ValueError` immediately so typos are
caught early.  A missing file (or empty file) returns an ``OsConfigProfile``
with all defaults (everything disabled).

build_overrides
---------------
Use the ``build_overrides`` top-level key to apply extra settings that are
only active on specific Windows builds.  Each entry key is the **minimum
build number** (inclusive) that triggers the override; all entries whose key
is ``<= current_build`` are applied in ascending key order so higher-build
entries win.

Example::

    # Applies to every build
    enable_auto_admin_logon: true

    build_overrides:
      26100:          # Win11 24H2 (build 26100) and later
        enable_boot_perf_autologger: true
      27000:          # Win11 25H2 (build ~27xxx) and later — overrides 26100 entry
        enable_boot_perf_autologger: false

Example ``osconfig.yaml``::

    disable_search_index: true
    disable_system_restore: true
    disable_memory_diagnostic_tasks: true
    disable_mcafee_tasks: true
"""

from __future__ import annotations

import sys
import os
from dataclasses import fields
from pathlib import Path
from typing import Dict, Any, Union

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .config import OsConfigProfile

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]

try:
    from lib.logger import get_module_logger as _get_logger
    _logger = _get_logger(__name__)
except Exception:  # pragma: no cover
    import logging as _logging
    _logger = _logging.getLogger(__name__)

_BUILD_OVERRIDES_KEY = "build_overrides"


def _get_current_build() -> int:
    """Return the current Windows build number from the registry, or 0 on error."""
    try:
        import winreg
        reg_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
            val, _ = winreg.QueryValueEx(key, "CurrentBuild")
            return int(val)
    except Exception:
        return 0


def _apply_build_overrides(
    base: Dict[str, Any],
    overrides_map: Any,
    current_build: int,
    valid_fields: set,
    yaml_path: Path,
) -> Dict[str, Any]:
    """
    Merge entries from *overrides_map* into *base* for all thresholds
    ``<= current_build``, applied in ascending threshold order.

    Args:
        base:           Base profile dict (modified in-place, a copy is returned).
        overrides_map:  The ``build_overrides`` value from the YAML.
        current_build:  The running system's build number.
        valid_fields:   Set of valid :class:`OsConfigProfile` field names.
        yaml_path:      Used only for error messages.

    Returns:
        Merged dict suitable for ``OsConfigProfile(**merged)``.
    """
    if not isinstance(overrides_map, dict):
        raise ValueError(
            f"osconfig.yaml: '{_BUILD_OVERRIDES_KEY}' must be a mapping of "
            f"{{build_number: {{field: value, ...}}}}, got "
            f"{type(overrides_map).__name__}: {yaml_path}"
        )

    merged = dict(base)

    # Sort thresholds ascending so higher-build entries override lower ones.
    for threshold in sorted(overrides_map.keys()):
        try:
            threshold_int = int(threshold)
        except (TypeError, ValueError):
            raise ValueError(
                f"osconfig.yaml: '{_BUILD_OVERRIDES_KEY}' key must be an integer "
                f"build number, got {threshold!r}: {yaml_path}"
            )

        if current_build < threshold_int:
            _logger.debug(
                "[profile_loader] build_overrides[%d] skipped "
                "(current_build=%d < threshold=%d)",
                threshold_int, current_build, threshold_int,
            )
            continue

        override_fields = overrides_map[threshold]
        if not isinstance(override_fields, dict):
            raise ValueError(
                f"osconfig.yaml: '{_BUILD_OVERRIDES_KEY}[{threshold}]' must be a "
                f"field mapping, got {type(override_fields).__name__}: {yaml_path}"
            )

        unknown = set(override_fields) - valid_fields
        if unknown:
            raise ValueError(
                f"osconfig.yaml: '{_BUILD_OVERRIDES_KEY}[{threshold}]' contains "
                f"unknown field(s): {sorted(unknown)}\n"
                f"Valid fields are: {sorted(valid_fields)}\n"
                f"File: {yaml_path}"
            )

        _logger.debug(
            "[profile_loader] build_overrides[%d] applied "
            "(current_build=%d >= threshold=%d): %s",
            threshold_int, current_build, threshold_int, list(override_fields),
        )
        merged.update(override_fields)

    return merged


def load_profile(yaml_path: Union[str, Path]) -> OsConfigProfile:
    """
    Load an :class:`OsConfigProfile` from *yaml_path*.

    Rules
    -----
    * If *yaml_path* does not exist, return ``OsConfigProfile()`` (all defaults).
    * If the file is empty or contains only comments, return ``OsConfigProfile()``.
    * Top-level keys must exactly match :class:`OsConfigProfile` field names,
      with the exception of ``build_overrides`` (see module docstring).
      Unknown keys raise :class:`ValueError` to catch typos early.
    * Values are passed verbatim to the dataclass constructor — booleans,
      strings, and integers are all supported.
    * ``build_overrides`` entries are merged in ascending build-number order;
      only entries whose key ``<= current Windows build`` are applied.

    Args:
        yaml_path: Path to the ``osconfig.yaml`` file.

    Returns:
        :class:`OsConfigProfile` populated from the YAML data.

    Raises:
        ImportError: If PyYAML is not installed.
        ValueError:  If the YAML contains unknown OsConfigProfile field names.
    """
    if _yaml is None:  # pragma: no cover
        raise ImportError(
            "PyYAML is required for load_profile(). "
            "Install it with: pip install pyyaml"
        )

    path = Path(yaml_path)
    if not path.exists():
        return OsConfigProfile()

    with path.open(encoding="utf-8") as fh:
        data = _yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise ValueError(
            f"osconfig.yaml must be a YAML mapping (got {type(data).__name__}): {path}"
        )

    # Separate build_overrides from the base profile fields.
    overrides_map = data.pop(_BUILD_OVERRIDES_KEY, None)

    valid_fields = {f.name for f in fields(OsConfigProfile)}
    unknown = set(data) - valid_fields
    if unknown:
        raise ValueError(
            f"osconfig.yaml contains unknown field(s): {sorted(unknown)}\n"
            f"Valid fields are: {sorted(valid_fields)}\n"
            f"File: {path}"
        )

    # Apply build-specific overrides when present.
    if overrides_map is not None:
        current_build = _get_current_build()
        _logger.debug(
            "[profile_loader] processing build_overrides (current_build=%d)",
            current_build,
        )
        data = _apply_build_overrides(data, overrides_map, current_build, valid_fields, path)

    return OsConfigProfile(**data)
