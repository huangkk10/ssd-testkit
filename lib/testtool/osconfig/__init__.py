"""
OsConfig Testtool Library

Provides OS-level configuration management for Windows test environments,
covering services, OneDrive, Windows Defender, power settings, boot options,
scheduled tasks, and system settings.

Usage (minimal)::

    from lib.testtool.osconfig import OsConfigController, OsConfigProfile

    profile = OsConfigProfile(
        disable_search_index=True,
        disable_windows_update=True,
        power_plan="high_performance",
        disable_monitor_timeout=True,
        disable_standby_timeout=True,
    )
    controller = OsConfigController(profile=profile)
    controller.apply()     # apply all settings, skips unsupported ones
    # ... run tests ...
    controller.revert()    # restore original values from snapshot

Phase 1 exports (base layer only):
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .exceptions import (
    OsConfigError,
    OsConfigPermissionError,
    OsConfigNotSupportedError,
    OsConfigTimeoutError,
    OsConfigStateError,
    OsConfigActionError,
)
from .os_compat import (
    WindowsBuildInfo,
    CAPABILITIES,
    get_build_info,
    is_supported,
    get_capability_description,
    list_unsupported_features,
)
from .registry_helper import (
    read_value,
    write_value,
    delete_value,
    key_exists,
    value_exists,
    read_value_safe,
    ensure_key,
    read_value_with_type,
    REG_SZ,
    REG_DWORD,
    REG_QWORD,
    REG_EXPAND_SZ,
    REG_MULTI_SZ,
    REG_BINARY,
)
from .actions import AbstractOsAction
from .config import OsConfigProfile
from .state_manager import OsConfigStateManager
from .controller import OsConfigController
from .profile_loader import load_profile

__version__ = "0.2.0"

__all__ = [
    # Exceptions
    "OsConfigError",
    "OsConfigPermissionError",
    "OsConfigNotSupportedError",
    "OsConfigTimeoutError",
    "OsConfigStateError",
    "OsConfigActionError",
    # OS compat
    "WindowsBuildInfo",
    "CAPABILITIES",
    "get_build_info",
    "is_supported",
    "get_capability_description",
    "list_unsupported_features",
    # Registry
    "read_value",
    "write_value",
    "delete_value",
    "key_exists",
    "value_exists",
    "read_value_safe",
    "ensure_key",
    "read_value_with_type",
    "REG_SZ",
    "REG_DWORD",
    "REG_QWORD",
    "REG_EXPAND_SZ",
    "REG_MULTI_SZ",
    "REG_BINARY",
    # Abstract base
    "AbstractOsAction",
    # Phase 5 – Controller layer
    "OsConfigProfile",
    "OsConfigStateManager",
    "OsConfigController",
    "load_profile",
]
