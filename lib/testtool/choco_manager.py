"""
lib/testtool/choco_manager.py

Python interface to Chocolatey for installing / uninstalling tools.
Reads package_meta.yaml to resolve versions and source paths automatically.

Usage:
    from lib.testtool.choco_manager import ChocoManager

    mgr = ChocoManager()
    result = mgr.install("windows-adk")           # default version
    result = mgr.install("windows-adk", "22621.0.0")
    result = mgr.uninstall("windows-adk")
    installed = mgr.is_installed("windows-adk")   # bool
    ver = mgr.get_installed_version("windows-adk") # str | None
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore  # lazy – only needed when reading YAML


@dataclass
class InstallResult:
    """Result of a choco install / uninstall operation."""
    success: bool
    tool_id: str
    version: str
    exit_code: int
    output: str          # combined stdout + stderr from choco
    error: str = ""      # set when success is False


class ChocoManagerError(RuntimeError):
    """Raised for configuration or setup errors (not choco exit-code failures)."""


class ChocoManager:
    """
    Thin Python wrapper around the Chocolatey CLI.

    Resolves the nupkg source directory automatically from
    `lib/testtool/<tool>/package_meta.yaml` and the SSD_TESTKIT_ROOT
    environment variable so that nupkg install scripts can locate
    large vendor installers.
    """

    #: Chocolatey exit codes that indicate "reboot required" but otherwise OK
    REBOOT_REQUIRED_EXIT_CODES = {3010}

    def __init__(self, project_root: Optional[str] = None) -> None:
        """
        Args:
            project_root: Absolute path to the ssd-testkit repo root.
                          Defaults to the SSD_TESTKIT_ROOT env var, or is
                          auto-detected relative to this file's location.
        """
        if project_root:
            self._root = Path(project_root)
        elif os.environ.get("SSD_TESTKIT_ROOT"):
            self._root = Path(os.environ["SSD_TESTKIT_ROOT"])
        else:
            # lib/testtool/choco_manager.py  ->  lib/testtool  ->  lib  ->  root
            self._root = Path(__file__).resolve().parent.parent.parent

        self._packages_dir = self._root / "bin" / "chocolatey" / "packages"
        self._testtool_dir = self._root / "lib" / "testtool"

    # ── public API ─────────────────────────────────────────────────────────

    def install(self, tool_id: str, version: Optional[str] = None) -> InstallResult:
        """
        Install a Chocolatey package from the local offline source.

        Args:
            tool_id:  Chocolatey package ID (e.g. "windows-adk").
            version:  Version string (e.g. "22621.0.0").
                      If None, uses the version marked ``default: true`` in
                      the tool's package_meta.yaml.

        Returns:
            InstallResult with success, exit_code, and choco output.
        """
        resolved_version = self._resolve_version(tool_id, version)
        source_dir = self._resolve_source_dir(tool_id, resolved_version)

        env = self._build_env()
        cmd = [
            "choco", "install", tool_id,
            "--source", str(source_dir),
            "--yes", "--no-progress", "--ignore-checksums",
        ]
        return self._run(cmd, tool_id, resolved_version, env)

    def uninstall(self, tool_id: str) -> InstallResult:
        """
        Uninstall a Chocolatey package.

        Returns:
            InstallResult with success, exit_code, and choco output.
        """
        installed_version = self.get_installed_version(tool_id) or ""
        env = self._build_env()
        cmd = ["choco", "uninstall", tool_id, "--yes", "--no-progress"]
        return self._run(cmd, tool_id, installed_version, env)

    def is_installed(self, tool_id: str) -> bool:
        """Return True if the package is currently installed."""
        return self.get_installed_version(tool_id) is not None

    def get_installed_version(self, tool_id: str) -> Optional[str]:
        """
        Return the installed version string, or None if not installed.

        Parses ``choco list`` output (Chocolatey v2+).
        """
        try:
            result = subprocess.run(
                ["choco", "list"],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].lower() == tool_id.lower():
                    return parts[1]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    # ── private helpers ────────────────────────────────────────────────────

    def _resolve_version(self, tool_id: str, version: Optional[str]) -> str:
        """Return *version* if supplied, else the default from package_meta.yaml."""
        if version:
            return version

        meta = self._load_package_meta(tool_id)
        for v in meta.get("versions", []):
            if v.get("default"):
                return str(v["version"])

        raise ChocoManagerError(
            f"No version specified and no default version found in "
            f"package_meta.yaml for '{tool_id}'."
        )

    def _resolve_source_dir(self, tool_id: str, version: str) -> Path:
        """
        Return the directory that contains the nupkg for *tool_id*/*version*.

        Chocolatey local folder source does NOT recurse into subdirectories,
        so we point it directly at ``packages/<id>/<version>/``.
        """
        source_dir = self._packages_dir / tool_id / version
        if not source_dir.is_dir():
            raise ChocoManagerError(
                f"Package source directory not found: {source_dir}\n"
                f"Expected: bin/chocolatey/packages/{tool_id}/{version}/"
            )
        return source_dir

    def _load_package_meta(self, tool_id: str) -> dict:
        """Load and parse the package_meta.yaml for the given tool."""
        # Map choco package id  (e.g. "windows-adk")  ->  testtool dir name
        meta_dir = self._testtool_dir / tool_id.replace("-", "_")
        meta_file = meta_dir / "package_meta.yaml"

        if not meta_file.is_file():
            raise ChocoManagerError(
                f"package_meta.yaml not found: {meta_file}\n"
                f"Create it under lib/testtool/{tool_id.replace('-', '_')}/"
            )

        if yaml is None:
            raise ChocoManagerError(
                "PyYAML is not installed. Run: pip install pyyaml"
            )

        with open(meta_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _build_env(self) -> dict:
        """Return os.environ copy with SSD_TESTKIT_ROOT set."""
        env = os.environ.copy()
        env["SSD_TESTKIT_ROOT"] = str(self._root)
        return env

    def _run(
        self,
        cmd: list[str],
        tool_id: str,
        version: str,
        env: dict,
    ) -> InstallResult:
        """Execute *cmd* and return an InstallResult."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=600,  # 10 min – large installers can be slow
            )
        except FileNotFoundError:
            return InstallResult(
                success=False,
                tool_id=tool_id,
                version=version,
                exit_code=-1,
                output="",
                error="'choco' command not found. Is Chocolatey installed?",
            )
        except subprocess.TimeoutExpired as exc:
            return InstallResult(
                success=False,
                tool_id=tool_id,
                version=version,
                exit_code=-1,
                output=exc.output or "",
                error=f"choco timed out after {exc.timeout}s",
            )

        combined = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0 or proc.returncode in self.REBOOT_REQUIRED_EXIT_CODES

        return InstallResult(
            success=ok,
            tool_id=tool_id,
            version=version,
            exit_code=proc.returncode,
            output=combined,
            error="" if ok else f"choco exited with code {proc.returncode}",
        )
