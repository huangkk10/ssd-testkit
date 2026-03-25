"""
ToolInstaller — reads a tools.yaml and installs each tool via ChocoManager.

tools.yaml schema::

    tools:
      - id: windows-adk      # ChocoManager tool_id
        reinstall: true       # true = uninstall first; false (default) = skip if installed
        version: "26100"      # optional; omit to use package_meta.yaml default: true
"""
from __future__ import annotations

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from lib.testtool.choco_manager import ChocoManager
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


@dataclass
class ToolEntry:
    id: str
    reinstall: bool = False
    version: Optional[str] = None   # None → use package_meta.yaml default: true


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
            ))
        return entries

    def install_all(self) -> None:
        """Install (or reinstall) every tool declared in tools.yaml."""
        mgr = ChocoManager()
        for entry in self._entries:
            if entry.reinstall and mgr.is_installed(entry.id):
                logger.info(f"[ToolInstaller] Uninstalling {entry.id} (reinstall=true)")
                result = mgr.uninstall(entry.id)
                assert result.success, (
                    f"Uninstall of '{entry.id}' failed "
                    f"(exit {result.exit_code}):\n{result.output}"
                )

            if not mgr.is_installed(entry.id):
                ver_label = entry.version or "(default)"
                logger.info(f"[ToolInstaller] Installing {entry.id} version={ver_label}")
                result = mgr.install(entry.id, version=entry.version)
                assert result.success, (
                    f"Install of '{entry.id}' failed "
                    f"(exit {result.exit_code}):\n{result.output}"
                )
            else:
                logger.info(f"[ToolInstaller] {entry.id} already installed — skip")

            assert mgr.is_installed(entry.id), \
                f"[ToolInstaller] '{entry.id}' not detected after install"
            logger.info(f"[ToolInstaller] {entry.id} ready")
