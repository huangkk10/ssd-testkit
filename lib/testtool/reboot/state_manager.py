"""
OsReboot State Manager

Handles cross-reboot state persistence using a JSON file on disk.
The state file is written with ``fsync`` to ensure data survives a
hard system reboot, and is read back on the next boot to resume the
reboot cycle sequence.

State file format::

    {
        "is_recovering": true,
        "current_cycle": 2,
        "total_cycles":  3,
        "last_reboot_timestamp": "2026-03-02T10:30:00"
    }

Example::

    manager = OsRebootStateManager('reboot_state.json')
    manager.save({'is_recovering': True, 'current_cycle': 1, 'total_cycles': 3})
    state = manager.load()
    print(state['current_cycle'])   # 1
    print(manager.is_recovering())  # True
    manager.clear()
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .exceptions import OsRebootStateError

# Default blank state returned when no state file exists.
_DEFAULT_STATE: Dict[str, Any] = {
    "is_recovering":        False,
    "current_cycle":        0,
    "total_cycles":         0,
    "last_reboot_timestamp": None,
}


class OsRebootStateManager:
    """
    Manages the JSON state file used to track reboot cycles across OS reboots.

    Args:
        state_file: Path to the JSON file.  Created on first :meth:`save`.
    """

    def __init__(self, state_file: str) -> None:
        self._path = Path(state_file)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load(self) -> Dict[str, Any]:
        """
        Load the state from disk.

        Returns:
            State dict.  If the file does not exist or cannot be parsed,
            returns a copy of :data:`_DEFAULT_STATE` (no exception raised).
        """
        if not self._path.exists():
            return dict(_DEFAULT_STATE)

        try:
            with open(self._path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise OsRebootStateError(
                f"Failed to load state file '{self._path}': {exc}"
            ) from exc

        # Back-fill any missing keys with defaults
        state = dict(_DEFAULT_STATE)
        state.update(data)
        return state

    def save(self, state: Dict[str, Any]) -> None:
        """
        Write *state* to disk and flush to ensure persistence across a hard reboot.

        A ``last_reboot_timestamp`` is automatically injected (ISO-8601 UTC).

        Args:
            state: Dict containing at minimum ``is_recovering``,
                   ``current_cycle``, and ``total_cycles``.

        Raises:
            OsRebootStateError: If writing or flushing the file fails.
        """
        payload = dict(state)
        payload['last_reboot_timestamp'] = datetime.utcnow().isoformat(
            timespec='seconds'
        )

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            raise OsRebootStateError(
                f"Failed to save state file '{self._path}': {exc}"
            ) from exc

    def clear(self) -> None:
        """
        Delete the state file if it exists.

        Raises:
            OsRebootStateError: If the file exists but cannot be removed.
        """
        if not self._path.exists():
            return
        try:
            self._path.unlink()
        except OSError as exc:
            raise OsRebootStateError(
                f"Failed to delete state file '{self._path}': {exc}"
            ) from exc

    def is_recovering(self) -> bool:
        """
        Return ``True`` if a previous cycle wrote ``is_recovering: true``
        to the state file (i.e. the OS just came back from a reboot).

        Does **not** raise on missing or corrupt files — returns ``False``.
        """
        try:
            state = self.load()
        except OsRebootStateError:
            return False
        return bool(state.get('is_recovering', False))
