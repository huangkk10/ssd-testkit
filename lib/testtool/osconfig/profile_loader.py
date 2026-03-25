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
from typing import Union

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .config import OsConfigProfile

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]


def load_profile(yaml_path: Union[str, Path]) -> OsConfigProfile:
    """
    Load an :class:`OsConfigProfile` from *yaml_path*.

    Rules
    -----
    * If *yaml_path* does not exist, return ``OsConfigProfile()`` (all defaults).
    * If the file is empty or contains only comments, return ``OsConfigProfile()``.
    * Keys must exactly match :class:`OsConfigProfile` field names.
      Unknown keys raise :class:`ValueError` to catch typos early.
    * Values are passed verbatim to the dataclass constructor — booleans,
      strings, and integers are all supported.

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

    valid_fields = {f.name for f in fields(OsConfigProfile)}
    unknown = set(data) - valid_fields
    if unknown:
        raise ValueError(
            f"osconfig.yaml contains unknown field(s): {sorted(unknown)}\n"
            f"Valid fields are: {sorted(valid_fields)}\n"
            f"File: {path}"
        )

    return OsConfigProfile(**data)
