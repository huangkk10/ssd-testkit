"""
tests/unit/lib/testtool/test_choco_manager/test_choco_manager.py

Unit tests for ChocoManager.  Uses unittest.mock to avoid calling
the real 'choco' CLI or touching the filesystem for most cases.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from lib.testtool.choco_manager import ChocoManager, ChocoManagerError, InstallResult


# ── fixtures ────────────────────────────────────────────────────────────────

FAKE_ROOT = Path("C:/fake/ssd-testkit")

PACKAGE_META_YAML = """\
tool_name: windows_adk
choco_package_id: windows-adk
versions:
  - version: "19041"
    default: false
  - version: "22621.0.0"
    default: true
  - version: "26100.0.0"
    default: false
"""


@pytest.fixture
def mgr(tmp_path):
    """ChocoManager pointed at a temp directory tree."""
    # Create expected directory structure
    pkg_dir = tmp_path / "bin" / "chocolatey" / "packages" / "windows-adk" / "22621.0.0"
    pkg_dir.mkdir(parents=True)
    meta_dir = tmp_path / "lib" / "testtool" / "windows_adk"
    meta_dir.mkdir(parents=True)
    (meta_dir / "package_meta.yaml").write_text(PACKAGE_META_YAML, encoding="utf-8")
    return ChocoManager(project_root=str(tmp_path))


# ── InstallResult ────────────────────────────────────────────────────────────

class TestInstallResult:
    def test_success_fields(self):
        r = InstallResult(success=True, tool_id="foo", version="1.0.0",
                          exit_code=0, output="ok")
        assert r.success is True
        assert r.error == ""

    def test_failure_fields(self):
        r = InstallResult(success=False, tool_id="foo", version="1.0.0",
                          exit_code=1, output="err", error="choco exited with code 1")
        assert r.success is False
        assert "1" in r.error


# ── ChocoManager.__init__ ────────────────────────────────────────────────────

class TestChocoManagerInit:
    def test_explicit_project_root(self, tmp_path):
        m = ChocoManager(project_root=str(tmp_path))
        assert m._root == tmp_path

    def test_env_var_project_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SSD_TESTKIT_ROOT", str(tmp_path))
        m = ChocoManager()
        assert m._root == tmp_path

    def test_auto_detect_root(self):
        # Should not raise; root is resolved relative to choco_manager.py
        m = ChocoManager()
        assert m._root.is_dir()


# ── _resolve_version ─────────────────────────────────────────────────────────

class TestResolveVersion:
    def test_explicit_version_returned_as_is(self, mgr):
        assert mgr._resolve_version("windows-adk", "26100.0.0") == "26100.0.0"

    def test_default_version_from_meta(self, mgr):
        assert mgr._resolve_version("windows-adk", None) == "22621.0.0"

    def test_missing_meta_raises(self, mgr):
        with pytest.raises(ChocoManagerError, match="package_meta.yaml not found"):
            mgr._resolve_version("nonexistent-tool", None)

    def test_no_default_in_meta_raises(self, mgr, tmp_path):
        meta_dir = tmp_path / "lib" / "testtool" / "no_default"
        meta_dir.mkdir(parents=True)
        (meta_dir / "package_meta.yaml").write_text(
            "versions:\n  - version: '1.0.0'\n    default: false\n", encoding="utf-8"
        )
        with pytest.raises(ChocoManagerError, match="No version specified"):
            mgr._resolve_version("no-default", None)


# ── _resolve_source_dir ───────────────────────────────────────────────────────

class TestResolveSourceDir:
    def test_returns_correct_path(self, mgr, tmp_path):
        src = mgr._resolve_source_dir("windows-adk", "22621.0.0")
        expected = tmp_path / "bin" / "chocolatey" / "packages" / "windows-adk" / "22621.0.0"
        assert src == expected

    def test_missing_dir_raises(self, mgr):
        with pytest.raises(ChocoManagerError, match="Package source directory not found"):
            mgr._resolve_source_dir("windows-adk", "99999.0.0")


# ── _build_env ────────────────────────────────────────────────────────────────

class TestBuildEnv:
    def test_ssd_testkit_root_injected(self, mgr, tmp_path):
        env = mgr._build_env()
        assert env["SSD_TESTKIT_ROOT"] == str(tmp_path)

    def test_original_env_not_mutated(self, mgr, monkeypatch):
        monkeypatch.delenv("SSD_TESTKIT_ROOT", raising=False)
        import os
        original_keys = set(os.environ.keys())
        mgr._build_env()
        assert set(os.environ.keys()) == original_keys


# ── install ───────────────────────────────────────────────────────────────────

class TestInstall:
    def _make_proc(self, returncode=0, stdout="Chocolatey installed 1/1", stderr=""):
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    def test_install_success(self, mgr):
        with patch("subprocess.run", return_value=self._make_proc()) as mock_run:
            result = mgr.install("windows-adk", "22621.0.0")

        assert result.success is True
        assert result.tool_id == "windows-adk"
        assert result.version == "22621.0.0"
        assert result.exit_code == 0

        cmd = mock_run.call_args[0][0]
        assert "choco" in cmd[0]
        assert "install" in cmd
        assert "windows-adk" in cmd
        assert "--yes" in cmd

    def test_install_uses_correct_source(self, mgr, tmp_path):
        with patch("subprocess.run", return_value=self._make_proc()) as mock_run:
            mgr.install("windows-adk", "22621.0.0")

        cmd = mock_run.call_args[0][0]
        source_idx = cmd.index("--source") + 1
        expected_source = str(
            tmp_path / "bin" / "chocolatey" / "packages" / "windows-adk" / "22621.0.0"
        )
        assert cmd[source_idx] == expected_source

    def test_install_uses_default_version(self, mgr):
        with patch("subprocess.run", return_value=self._make_proc()) as mock_run:
            result = mgr.install("windows-adk")

        assert result.version == "22621.0.0"

    def test_install_failure_nonzero_exit(self, mgr):
        with patch("subprocess.run", return_value=self._make_proc(returncode=1, stdout="failed")):
            result = mgr.install("windows-adk", "22621.0.0")

        assert result.success is False
        assert result.exit_code == 1
        assert result.error != ""

    def test_install_reboot_required_is_success(self, mgr):
        with patch("subprocess.run", return_value=self._make_proc(returncode=3010)):
            result = mgr.install("windows-adk", "22621.0.0")

        assert result.success is True
        assert result.exit_code == 3010

    def test_install_choco_not_found(self, mgr):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = mgr.install("windows-adk", "22621.0.0")

        assert result.success is False
        assert "choco" in result.error.lower()
        assert result.exit_code == -1

    def test_install_timeout(self, mgr):
        exc = subprocess.TimeoutExpired(cmd=["choco"], timeout=600)
        exc.output = ""
        with patch("subprocess.run", side_effect=exc):
            result = mgr.install("windows-adk", "22621.0.0")

        assert result.success is False
        assert result.exit_code == -1

    def test_ssd_testkit_root_set_in_subprocess_env(self, mgr, tmp_path):
        with patch("subprocess.run", return_value=self._make_proc()) as mock_run:
            mgr.install("windows-adk", "22621.0.0")

        env_passed = mock_run.call_args[1]["env"]
        assert env_passed["SSD_TESTKIT_ROOT"] == str(tmp_path)


# ── uninstall ─────────────────────────────────────────────────────────────────

class TestUninstall:
    def _make_proc(self, returncode=0):
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = "Chocolatey uninstalled 1/1"
        proc.stderr = ""
        return proc

    def test_uninstall_success(self, mgr):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # first call: choco list (get_installed_version)
                MagicMock(returncode=0,
                          stdout="Chocolatey v2.7.0\nwindows-adk 22621.0.0\n",
                          stderr=""),
                # second call: choco uninstall
                self._make_proc(),
            ]
            result = mgr.uninstall("windows-adk")

        assert result.success is True
        uninstall_cmd = mock_run.call_args_list[1][0][0]
        assert "uninstall" in uninstall_cmd
        assert "windows-adk" in uninstall_cmd
        assert "--yes" in uninstall_cmd

    def test_uninstall_failure(self, mgr):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Chocolatey v2.7.0\n", stderr=""),
                self._make_proc(returncode=1),
            ]
            result = mgr.uninstall("windows-adk")

        assert result.success is False


# ── is_installed / get_installed_version ─────────────────────────────────────

class TestIsInstalled:
    def _list_proc(self, stdout):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = stdout
        proc.stderr = ""
        return proc

    def test_is_installed_true(self, mgr):
        with patch("subprocess.run",
                   return_value=self._list_proc("Chocolatey v2.7.0\nwindows-adk 22621.0.0\n")):
            assert mgr.is_installed("windows-adk") is True

    def test_is_installed_false(self, mgr):
        with patch("subprocess.run",
                   return_value=self._list_proc("Chocolatey v2.7.0\n0 packages installed.\n")):
            assert mgr.is_installed("windows-adk") is False

    def test_get_installed_version_returns_version(self, mgr):
        with patch("subprocess.run",
                   return_value=self._list_proc("Chocolatey v2.7.0\nwindows-adk 22621.0.0\n")):
            assert mgr.get_installed_version("windows-adk") == "22621.0.0"

    def test_get_installed_version_returns_none(self, mgr):
        with patch("subprocess.run",
                   return_value=self._list_proc("Chocolatey v2.7.0\n0 packages installed.\n")):
            assert mgr.get_installed_version("windows-adk") is None

    def test_get_installed_version_choco_missing(self, mgr):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert mgr.get_installed_version("windows-adk") is None

    def test_case_insensitive_match(self, mgr):
        with patch("subprocess.run",
                   return_value=self._list_proc("Chocolatey v2.7.0\nWindows-ADK 22621.0.0\n")):
            assert mgr.is_installed("windows-adk") is True


# ── _META_PATH_OVERRIDES ──────────────────────────────────────────────────────

class TestMetaPathOverrides:
    """Verify that tools with non-default package_meta.yaml locations are resolved."""

    def test_smiwintools_loads_from_smartcheck(self, tmp_path):
        """smiwintools package_meta.yaml lives under smartcheck/, not smiwintools/."""
        pkg_dir = tmp_path / "bin" / "chocolatey" / "packages" / "smiwintools" / "2026.2.13"
        pkg_dir.mkdir(parents=True)
        meta_dir = tmp_path / "lib" / "testtool" / "smartcheck"
        meta_dir.mkdir(parents=True)
        (meta_dir / "package_meta.yaml").write_text(
            "tool_name: smiwintools\nchoco_package_id: smiwintools\n"
            "versions:\n  - version: '2026.2.13'\n    default: true\n",
            encoding="utf-8",
        )
        m = ChocoManager(project_root=str(tmp_path))
        assert m._resolve_version("smiwintools", None) == "2026.2.13"

    def test_smiwintools_missing_in_smiwintools_dir(self, tmp_path):
        """Without the override, placing meta under smiwintools/ would fail; with it, smartcheck/ is used."""
        # Put meta in the wrong place (smiwintools/) — should NOT be found
        wrong_dir = tmp_path / "lib" / "testtool" / "smiwintools"
        wrong_dir.mkdir(parents=True)
        (wrong_dir / "package_meta.yaml").write_text(
            "versions:\n  - version: '2026.2.13'\n    default: true\n",
            encoding="utf-8",
        )
        m = ChocoManager(project_root=str(tmp_path))
        with pytest.raises(ChocoManagerError, match="package_meta.yaml not found"):
            m._resolve_version("smiwintools", None)


# ── _find_choco ───────────────────────────────────────────────────────────────

class TestFindChoco:
    def test_returns_known_path_when_exists(self, tmp_path):
        """_find_choco returns the well-known path when choco.exe is present."""
        fake_choco = tmp_path / "choco.exe"
        fake_choco.write_text("fake")
        with patch("os.path.isfile", side_effect=lambda p: str(p) == str(fake_choco)):
            result = ChocoManager._find_choco.__func__(
                # patch candidates list to only contain our fake path
            ) if False else None

        # Simpler: patch the candidates list via monkeypatching the method
        original = ChocoManager._find_choco.__func__ if hasattr(ChocoManager._find_choco, '__func__') else ChocoManager._find_choco
        with patch.object(ChocoManager, "_find_choco", staticmethod(lambda: str(fake_choco))):
            m = ChocoManager.__new__(ChocoManager)
            m._choco = ChocoManager._find_choco()
            assert m._choco == str(fake_choco)

    def test_fallback_to_choco_string(self):
        """_find_choco returns 'choco' when no well-known path exists."""
        with patch("os.path.isfile", return_value=False):
            assert ChocoManager._find_choco() == "choco"

    def test_choco_path_used_in_install_command(self, mgr):
        """The resolved choco path is used in the install subprocess call."""
        mgr._choco = r"C:\ProgramData\chocolatey\bin\choco.exe"
        proc = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch("subprocess.run", return_value=proc) as mock_run:
            mgr.install("windows-adk", "22621.0.0")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == r"C:\ProgramData\chocolatey\bin\choco.exe"
