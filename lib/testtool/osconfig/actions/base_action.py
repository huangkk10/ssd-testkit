"""
OsConfig Abstract Base Action

Defines the common interface that every OS-configuration Action must implement.
All concrete actions (``SearchIndexAction``, ``DefenderAction``, etc.) inherit
from :class:`AbstractOsAction`.

Design contract
---------------
* ``apply()``  – apply the setting; idempotent (check first, skip if already done).
* ``revert()`` – restore the previous value from the snapshot taken at ``apply()``
                 time.  If no snapshot exists, logs a warning and does nothing.
* ``check()``  – return ``True`` when the system is already in the target state,
                 ``False`` otherwise.  Must never modify any system state.
* ``supported_on(build_info)`` – class-method; return ``True`` when the action
                 can be applied on the given OS build/edition.

Snapshot / revert pattern
-------------------------
Before making any system change, ``apply()`` should save the current value via
the ``state_manager`` so ``revert()`` can restore it.  Actions that do not have
a revertable state (e.g. one-way bcdedit changes) should document this and
implement ``revert()`` as a no-op with a warning.
"""

from __future__ import annotations

import sys
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.logger import get_module_logger
from ..os_compat import WindowsBuildInfo

logger = get_module_logger(__name__)


class AbstractOsAction(ABC):
    """
    Abstract base class for all OS-configuration actions.

    Subclasses must implement :meth:`apply`, :meth:`revert`, :meth:`check`,
    and :meth:`supported_on`.

    Args:
        snapshot_store: Optional mutable dict used as an in-memory snapshot
            store.  Pass the same dict to all actions so they share one
            snapshot namespace inside a controller run.  If ``None``, each
            action maintains its own private snapshot dict.

    Example::

        build = get_build_info()
        action = SearchIndexAction()
        if not action.check():
            action.apply()
        # later:
        action.revert()
    """

    # Subclasses should override this with a short identifier used in logs.
    #: Short name used in log messages.  Override in each subclass.
    name: str = "AbstractOsAction"

    def __init__(self, snapshot_store: Optional[Dict[str, Any]] = None) -> None:
        self._snapshot: Dict[str, Any] = snapshot_store if snapshot_store is not None else {}

    # ------------------------------------------------------------------ #
    # Abstract methods – must be implemented by every concrete action      #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def apply(self) -> None:
        """
        Apply the OS configuration change.

        Implementation rules:
        - Call :meth:`check` first; if already in target state, return early.
        - Save current state to ``self._snapshot`` before making changes.
        - Raise :class:`~lib.testtool.osconfig.exceptions.OsConfigPermissionError`
          on access-denied, or
          :class:`~lib.testtool.osconfig.exceptions.OsConfigActionError`
          on other failures.
        """

    @abstractmethod
    def revert(self) -> None:
        """
        Revert the change made by :meth:`apply`.

        Implementation rules:
        - Read the saved value from ``self._snapshot``.
        - If no snapshot exists, log a warning and return without raising.
        - Idempotent: safe to call multiple times.
        """

    @abstractmethod
    def check(self) -> bool:
        """
        Return ``True`` when the system is already in the target (applied) state.

        Must be side-effect-free.
        """

    @classmethod
    @abstractmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool:
        """
        Return ``True`` when this action can be applied on *build_info*.

        Args:
            build_info: OS version snapshot from
                :func:`~lib.testtool.osconfig.os_compat.get_build_info`.
        """

    # ------------------------------------------------------------------ #
    # Non-abstract helpers available to every concrete action              #
    # ------------------------------------------------------------------ #

    def _log_apply_start(self) -> None:
        logger.info(f"[{self.name}] Applying …")

    def _log_apply_skip(self) -> None:
        logger.info(f"[{self.name}] Already in target state – skipping apply.")

    def _log_apply_done(self) -> None:
        logger.info(f"[{self.name}] Applied successfully.")

    def _log_revert_start(self) -> None:
        logger.info(f"[{self.name}] Reverting …")

    def _log_revert_skip(self) -> None:
        logger.warning(
            f"[{self.name}] No snapshot found – cannot revert. "
            "Was apply() called before revert()?"
        )

    def _log_revert_done(self) -> None:
        logger.info(f"[{self.name}] Reverted successfully.")

    def _save_snapshot(self, key: str, value: Any) -> None:
        """Save *value* under *key* in the internal snapshot store."""
        self._snapshot[key] = value
        logger.debug(f"[{self.name}] snapshot saved: {key} = {value!r}")

    def _load_snapshot(self, key: str, default: Any = None) -> Any:
        """Load a value from the snapshot store, returning *default* if missing."""
        return self._snapshot.get(key, default)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
