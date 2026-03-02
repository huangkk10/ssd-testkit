"""
OsConfig Registry Helper

Thin wrapper around the ``winreg`` stdlib module that:

- Centralises all registry read/write/delete operations.
- Provides a clear mocking boundary for unit tests (mock this module's
  functions instead of patching ``winreg`` directly).
- Handles key creation automatically when writing.
- Raises :class:`~lib.testtool.osconfig.exceptions.OsConfigPermissionError`
  on access-denied errors so callers don't need to inspect raw ``OSError``
  error codes.

Supported hives (string aliases)::

    "HKLM"  →  winreg.HKEY_LOCAL_MACHINE
    "HKCU"  →  winreg.HKEY_CURRENT_USER
    "HKCR"  →  winreg.HKEY_CLASSES_ROOT
    "HKU"   →  winreg.HKEY_USERS

Usage::

    from lib.testtool.osconfig.registry_helper import (
        read_value, write_value, delete_value,
        key_exists, value_exists, ensure_key,
    )

    write_value("HKLM", r"SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive",
                "DisableFileSyncNGSC", 1, REG_DWORD)

    val = read_value("HKLM",
                     r"SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive",
                     "DisableFileSyncNGSC")
    print(val)  # 1
"""

import winreg
import sys
import os
from typing import Any, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from .exceptions import OsConfigPermissionError, OsConfigActionError

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Public constants – re-export common REG_* types so callers don't need to
# import winreg themselves.
# ---------------------------------------------------------------------------
REG_SZ       = winreg.REG_SZ
REG_DWORD    = winreg.REG_DWORD
REG_QWORD    = winreg.REG_QWORD
REG_EXPAND_SZ = winreg.REG_EXPAND_SZ
REG_MULTI_SZ = winreg.REG_MULTI_SZ
REG_BINARY   = winreg.REG_BINARY

# ---------------------------------------------------------------------------
# Hive mapping
# ---------------------------------------------------------------------------
_HIVE_MAP = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKU":  winreg.HKEY_USERS,
}


def _resolve_hive(hive: str) -> int:
    """Convert a hive alias string to a winreg constant."""
    hive_upper = hive.upper().strip("\\")
    if hive_upper not in _HIVE_MAP:
        raise ValueError(
            f"Unknown hive '{hive}'. "
            f"Supported: {list(_HIVE_MAP.keys())}"
        )
    return _HIVE_MAP[hive_upper]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_value(hive: str, key_path: str, value_name: str) -> Any:
    """
    Read a registry value.

    Args:
        hive:       Hive alias (e.g. ``"HKLM"``).
        key_path:   Registry key path (e.g.
                    ``r"SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive"``).
        value_name: Value name to read.

    Returns:
        The value data (type depends on the registry value type).

    Raises:
        FileNotFoundError: If the key or value does not exist.
        OsConfigPermissionError: If access is denied.
        OsConfigActionError: On any other registry error.
    """
    h = _resolve_hive(hive)
    try:
        with winreg.OpenKey(h, key_path, 0, winreg.KEY_READ) as key:
            data, _ = winreg.QueryValueEx(key, value_name)
            logger.debug(f"registry_helper.read_value: {hive}\\{key_path}\\{value_name} = {data!r}")
            return data
    except FileNotFoundError:
        raise
    except PermissionError as exc:
        raise OsConfigPermissionError(
            f"Access denied reading {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc
    except OSError as exc:
        raise OsConfigActionError(
            f"Registry read failed for {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc


def write_value(
    hive: str,
    key_path: str,
    value_name: str,
    value: Any,
    value_type: int = REG_DWORD,
) -> None:
    """
    Write a registry value, creating the key hierarchy if necessary.

    Args:
        hive:        Hive alias (e.g. ``"HKLM"``).
        key_path:    Registry key path.
        value_name:  Value name to write.
        value:       Data to write.
        value_type:  Registry value type constant (default: ``REG_DWORD``).

    Raises:
        OsConfigPermissionError: If access is denied (e.g. Tamper Protection).
        OsConfigActionError: On any other registry error.
    """
    h = _resolve_hive(hive)
    try:
        ensure_key(hive, key_path)
        with winreg.OpenKey(h, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, value_name, 0, value_type, value)
            logger.debug(
                f"registry_helper.write_value: {hive}\\{key_path}\\{value_name} "
                f"= {value!r} (type={value_type})"
            )
    except PermissionError as exc:
        raise OsConfigPermissionError(
            f"Access denied writing {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc
    except OSError as exc:
        raise OsConfigActionError(
            f"Registry write failed for {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc


def delete_value(hive: str, key_path: str, value_name: str) -> None:
    """
    Delete a registry value.  No-op if the value does not exist.

    Raises:
        OsConfigPermissionError: If access is denied.
        OsConfigActionError: On any other registry error.
    """
    h = _resolve_hive(hive)
    try:
        with winreg.OpenKey(h, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, value_name)
            logger.debug(f"registry_helper.delete_value: {hive}\\{key_path}\\{value_name}")
    except FileNotFoundError:
        # Value already absent – treat as success (idempotent)
        pass
    except PermissionError as exc:
        raise OsConfigPermissionError(
            f"Access denied deleting {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc
    except OSError as exc:
        raise OsConfigActionError(
            f"Registry delete failed for {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc


def key_exists(hive: str, key_path: str) -> bool:
    """
    Return ``True`` if the registry key exists.

    Args:
        hive:     Hive alias.
        key_path: Registry key path.
    """
    h = _resolve_hive(hive)
    try:
        with winreg.OpenKey(h, key_path, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False
    except PermissionError:
        # Key exists but we can't open it
        return True


def value_exists(hive: str, key_path: str, value_name: str) -> bool:
    """
    Return ``True`` if *value_name* exists under *key_path*.

    Args:
        hive:       Hive alias.
        key_path:   Registry key path.
        value_name: Value name to check.
    """
    try:
        read_value(hive, key_path, value_name)
        return True
    except FileNotFoundError:
        return False


def read_value_safe(
    hive: str,
    key_path: str,
    value_name: str,
    default: Any = None,
) -> Any:
    """
    Read a registry value, returning *default* instead of raising if not found.

    Useful for taking a snapshot before overwriting (revert pattern).
    """
    try:
        return read_value(hive, key_path, value_name)
    except (FileNotFoundError, OsConfigActionError):
        return default


def ensure_key(hive: str, key_path: str) -> None:
    """
    Create *key_path* (and all intermediate keys) if it does not exist.

    Equivalent to ``reg add <key_path> /f`` but Python-native.

    Raises:
        OsConfigPermissionError: If access is denied.
        OsConfigActionError: On any other registry error.
    """
    h = _resolve_hive(hive)
    try:
        # CreateKeyEx is idempotent – no-op if key already exists
        key = winreg.CreateKeyEx(h, key_path, 0, winreg.KEY_WRITE)
        key.Close()
        logger.debug(f"registry_helper.ensure_key: {hive}\\{key_path}")
    except PermissionError as exc:
        raise OsConfigPermissionError(
            f"Access denied creating key {hive}\\{key_path}: {exc}"
        ) from exc
    except OSError as exc:
        raise OsConfigActionError(
            f"Failed to create key {hive}\\{key_path}: {exc}"
        ) from exc


def read_value_with_type(
    hive: str, key_path: str, value_name: str
) -> Tuple[Any, int]:
    """
    Read a registry value and return ``(data, type_id)`` tuple.

    Useful when you need to preserve the original type during snapshot/revert.

    Raises:
        FileNotFoundError: If the key or value does not exist.
        OsConfigPermissionError: If access is denied.
        OsConfigActionError: On any other registry error.
    """
    h = _resolve_hive(hive)
    try:
        with winreg.OpenKey(h, key_path, 0, winreg.KEY_READ) as key:
            data, reg_type = winreg.QueryValueEx(key, value_name)
            return data, reg_type
    except FileNotFoundError:
        raise
    except PermissionError as exc:
        raise OsConfigPermissionError(
            f"Access denied reading {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc
    except OSError as exc:
        raise OsConfigActionError(
            f"Registry read failed for {hive}\\{key_path}\\{value_name}: {exc}"
        ) from exc
