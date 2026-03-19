"""
DotnetInstaller — Controller

Thin threading.Thread wrapper around :class:`DotnetInstallerProcessManager`
for use in parallel test scaffolding.  For most test preconditions the
blocking :meth:`ensure_dotnet_runtime` helper is simpler.
"""

from __future__ import annotations

import threading
from typing import Optional

from .config import DotnetInstallerConfig
from .process_manager import DotnetInstallerProcessManager


class DotnetInstallerController(threading.Thread):
    """
    Threading controller for .NET Runtime installation.

    Args:
        config: Optional :class:`DotnetInstallerConfig`.  Defaults are used if omitted.

    Attributes:
        status (Optional[bool]):
            ``None`` before :meth:`start`, ``True`` on success, ``False`` on failure.

    Example::

        ctrl = DotnetInstallerController()
        ctrl.start()
        ctrl.join(timeout=300)
        assert ctrl.status is True
    """

    def __init__(self, config: Optional[DotnetInstallerConfig] = None) -> None:
        super().__init__(daemon=True)
        self._cfg = config or DotnetInstallerConfig()
        self._mgr = DotnetInstallerProcessManager(self._cfg)
        self.status: Optional[bool] = None

    def run(self) -> None:
        self.status = self._mgr.ensure()
