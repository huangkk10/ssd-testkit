"""
OsConfig — OsConfigStateManager

Persists and restores the snapshot dictionary produced by action classes
to/from a JSON file on disk.

This allows a test run to survive a reboot: ``apply_all()`` dumps the
snapshot, and after reboot ``revert_all()`` loads it back and restores every
original setting.

Usage::

    from lib.testtool.osconfig.state_manager import OsConfigStateManager

    mgr = OsConfigStateManager(path=r"C:\\testlogs\\osconfig_snapshot.json")

    # Before apply:
    mgr.save({"auto_reboot_orig": 1, "fast_startup_orig": 1})

    # After reboot, before revert:
    snap = mgr.load()   # → {"auto_reboot_orig": 1, "fast_startup_orig": 1}
    mgr.delete()        # clean up after successful revert
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from .exceptions import OsConfigStateError

logger = get_module_logger(__name__)

_DEFAULT_PATH = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "osconfig_snapshot.json"


class OsConfigStateManager:
    """
    Persist the action snapshot dictionary to a JSON file.

    Args:
        path: Path to the JSON snapshot file.
              Defaults to ``%TEMP%\\osconfig_snapshot.json``.
    """

    def __init__(self, path: Optional[os.PathLike] = None) -> None:
        self._path = Path(path) if path is not None else _DEFAULT_PATH

    @property
    def path(self) -> Path:
        """Return the resolved snapshot file path."""
        return self._path

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def save(self, snapshot: Dict[str, Any]) -> None:
        """
        Serialise *snapshot* to JSON and write to :attr:`path`.

        The parent directory is created if it does not exist.

        Args:
            snapshot: Dict mapping snapshot keys to their original values.

        Raises:
            OsConfigStateError: If the file cannot be written.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2)
            logger.debug(f"[OsConfigStateManager] Snapshot saved → {self._path}")
        except OSError as exc:
            raise OsConfigStateError(
                f"Cannot write snapshot to {self._path}: {exc}"
            ) from exc

    def load(self) -> Dict[str, Any]:
        """
        Load and deserialise the snapshot from :attr:`path`.

        Returns:
            The snapshot dictionary.

        Raises:
            OsConfigStateError: If the file is missing or cannot be parsed.
        """
        if not self._path.exists():
            raise OsConfigStateError(
                f"Snapshot file not found: {self._path}"
            )
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            logger.debug(f"[OsConfigStateManager] Snapshot loaded ← {self._path}")
            return data
        except (OSError, json.JSONDecodeError) as exc:
            raise OsConfigStateError(
                f"Cannot read snapshot from {self._path}: {exc}"
            ) from exc

    def exists(self) -> bool:
        """Return ``True`` when the snapshot file is present on disk."""
        return self._path.exists()

    def delete(self) -> None:
        """
        Remove the snapshot file if it exists.

        Silently ignores the call when the file is already absent.

        Raises:
            OsConfigStateError: If the file exists but cannot be removed.
        """
        if not self._path.exists():
            return
        try:
            self._path.unlink()
            logger.debug(f"[OsConfigStateManager] Snapshot deleted: {self._path}")
        except OSError as exc:
            raise OsConfigStateError(
                f"Cannot delete snapshot {self._path}: {exc}"
            ) from exc
