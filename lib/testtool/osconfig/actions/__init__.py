# lib/testtool/osconfig/actions/__init__.py
"""
OsConfig Actions sub-package.

Each module in this package implements one OS configuration action via a
concrete subclass of :class:`~lib.testtool.osconfig.actions.base_action.AbstractOsAction`.
"""

from .base_action import AbstractOsAction
from ._base_service_action import BaseServiceAction

# ── Phase 2: Service Actions ──────────────────────────────────────────────
from .search_index import SearchIndexAction
from .sysmain import SysMainAction
from .windows_update import WindowsUpdateAction
from .wer import WerAction
from .telemetry import TelemetryAction
from .pcasvc import PcaSvcAction

__all__ = [
    # Base classes
    "AbstractOsAction",
    "BaseServiceAction",
    # Phase 2 – Services
    "SearchIndexAction",
    "SysMainAction",
    "WindowsUpdateAction",
    "WerAction",
    "TelemetryAction",
    "PcaSvcAction",
]
