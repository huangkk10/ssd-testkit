"""
ToolInstaller — reads a tools.yaml and installs each tool via ChocoManager.

tools.yaml schema::

    tools:
      - id: smicli        # ChocoManager tool_id
        reinstall: false   # false (default) = skip if installed
        phase: pre_runcard # "pre_runcard" = install in setup before RunCard init
                           # "test" (default) = install in test_01_precondition
      - id: windows-adk
        reinstall: true    # true = uninstall first
        version: "26100"   # optional; omit to use package_meta.yaml default: true
"""
from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml as _yaml

from lib.testtool.choco_manager import ChocoManager
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


@dataclass
class ToolEntry:
    id: str
    reinstall: bool = False
    version: Optional[str] = None   # None → use package_meta.yaml default: true
    phase: str = "test"             # "pre_runcard" | "test" (default)
    env: Dict[str, str] = field(default_factory=dict)  # env vars to inject into current process


class ToolInstaller:
    """
    Read a tools.yaml and install/reinstall each tool via ChocoManager.

    Usage::

        installer = ToolInstaller(Path(__file__).parent / "Config" / "tools.yaml")
        installer.install_all()

    tools.yaml fields:

    - ``id``        (str, required)  — ChocoManager tool_id, matches package_meta.yaml key.
    - ``reinstall`` (bool, default False) — if True, uninstall first then always install;
                    if False, skip when already installed.
    - ``version``   (str, optional) — pin a specific version; omit to use the
                    version marked ``default: true`` in package_meta.yaml.
    - ``phase``     (str, default ``"test"``) — ``"pre_runcard"`` to install
                    before RunCard initialisation in ``setup_test_class``;
                    ``"test"`` (default) to install inside ``test_01_precondition``.
    - ``env``      (dict, optional) — environment variables to set in the current
                    process after the tool is ready (whether installed or skipped).
                    Useful when the Chocolatey installer sets machine-level registry
                    vars that the current process cannot see until restarted.
    """

    def __init__(self, yaml_path: str | Path) -> None:
        self._path = Path(yaml_path)
        self._entries: List[ToolEntry] = self._load()

    def _load(self) -> List[ToolEntry]:
        if not self._path.exists():
            logger.warning(
                f"[ToolInstaller] tools.yaml not found: {self._path} — no tools to install"
            )
            return []
        with self._path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = []
        for item in data.get("tools", []):
            if "id" not in item:
                raise ValueError(
                    f"[ToolInstaller] tools.yaml entry missing required 'id' field: {item}"
                )
            entries.append(ToolEntry(
                id=item["id"],
                reinstall=bool(item.get("reinstall", False)),
                version=item.get("version") or None,
                phase=str(item.get("phase", "test")),
                env=dict(item.get("env") or {}),
            ))
        return entries

    def install_pre_runcard(self) -> None:
        """Install only tools with ``phase: pre_runcard`` (call before RunCard init)."""
        self._install([e for e in self._entries if e.phase == "pre_runcard"])

    def install_all(self) -> None:
        """Install (or reinstall) every tool declared in tools.yaml."""
        self._install(self._entries)

    @staticmethod
    def _inject_env_from_meta(tool_id: str) -> None:
        """
        Read ``install_dir`` and ``env_var`` from the tool's ``package_meta.yaml``
        and inject ``env_var=<install_dir>\\<binary>`` into the current process.

        This handles the common case where Chocolatey sets a machine-level env
        var that the current process cannot see until a new process is started.
        No-op if the tool has no ``package_meta.yaml`` or no ``env_var`` field.
        """
        # Locate package_meta.yaml next to the tool's __init__.py
        # e.g. lib/testtool/smicli/package_meta.yaml
        here = Path(__file__).parent  # lib/testtool/
        meta_path = here / tool_id.replace("-", "_") / "package_meta.yaml"
        if not meta_path.exists():
            return
        try:
            with meta_path.open(encoding="utf-8") as f:
                meta = _yaml.safe_load(f) or {}
        except Exception:
            return
        env_var = meta.get("env_var")
        install_dir = meta.get("install_dir")
        if not env_var or not install_dir:
            return
        binaries = meta.get("binaries", [])
        exe_name = binaries[0] if binaries else ""
        if not exe_name:
            return
        exe_path = str(Path(install_dir) / exe_name)
        if env_var not in os.environ:
            os.environ[env_var] = exe_path
            logger.debug(f"[ToolInstaller] env auto-set from meta: {env_var}={exe_path}")

    def _install(self, entries: "List[ToolEntry]") -> None:
        """Core install loop for a given subset of entries."""
        mgr = ChocoManager()
        for entry in entries:
            if entry.reinstall and mgr.is_installed(entry.id):
                logger.info(f"[ToolInstaller] Uninstalling {entry.id} (reinstall=true)")
                result = mgr.uninstall(entry.id)
                assert result.success, (
                    f"Uninstall of '{entry.id}' failed "
                    f"(exit {result.exit_code}):\n{result.output}"
                    + (f"\n{result.error}" if result.error else "")
                )

            if not mgr.is_installed(entry.id):
                ver_label = entry.version or "(default)"
                logger.info(f"[ToolInstaller] Installing {entry.id} version={ver_label}")
                result = mgr.install(entry.id, version=entry.version)
                assert result.success, (
                    f"Install of '{entry.id}' failed "
                    f"(exit {result.exit_code}):\n{result.output}"
                    + (f"\n{result.error}" if result.error else "")
                )
            else:
                logger.info(f"[ToolInstaller] {entry.id} already installed — skip")

            assert mgr.is_installed(entry.id), \
                f"[ToolInstaller] '{entry.id}' not detected after install"
            logger.info(f"[ToolInstaller] {entry.id} ready")

            # 1. Auto-inject env var from package_meta.yaml (install_dir + env_var)
            self._inject_env_from_meta(entry.id)
            # 2. Apply explicit overrides from tools.yaml (takes precedence)
            for var, val in entry.env.items():
                os.environ[var] = val
                logger.debug(f"[ToolInstaller] env override: {var}={val}")
