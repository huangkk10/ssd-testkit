"""
PythonInstaller Controller Integration Tests

Run the real Python installer on a live Windows machine.
Nothing is mocked — these tests perform actual install / uninstall operations.

Requirements
------------
- Windows OS
- Administrator privileges
- Internet access OR PYTHON_INSTALLER_PATH pointing to a local installer

Safety notes
------------
- `add_to_path` is always False to avoid polluting the system PATH.
- Each test installs into an isolated directory (via `isolated_install_dir` fixture)
  which is cleaned up by pytest's `tmp_path` machinery.
- Default test version: Python 3.11 (override with PYTHON_INSTALLER_VERSION).

Run integration tests
---------------------
    pytest tests/integration/lib/testtool/test_python_installer/ -v -m "integration"
"""

import sys
import time
import threading
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.testtool.python_installer import PythonInstallerController
from lib.testtool.python_installer.process_manager import PythonInstallerProcessManager
from lib.testtool.python_installer.exceptions import (
    PythonInstallerError,
    PythonInstallerInstallError,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_controller(env: dict, install_dir: Path, **extra) -> PythonInstallerController:
    """Build a controller using the session environment + override kwargs."""
    return PythonInstallerController(
        version=env['version'],
        architecture=env['architecture'],
        install_path=str(install_dir),
        installer_path=env['installer_path'],
        download_dir=env['download_dir'],
        add_to_path=False,           # never pollute system PATH during tests
        timeout_seconds=env['timeout'],
        **extra,
    )


def _make_process_manager(env: dict, install_dir: Path) -> PythonInstallerProcessManager:
    """Build a process manager for lower-level tests."""
    return PythonInstallerProcessManager(
        version=env['version'],
        architecture=env['architecture'],
        install_path=str(install_dir),
        installer_path=env['installer_path'],
        download_dir=env['download_dir'],
        add_to_path=False,
        timeout_seconds=env['timeout'],
    )


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_python_installer
@pytest.mark.slow
class TestPythonInstallerControllerIntegration:
    """
    End-to-end PythonInstallerController tests against a real Python installer.
    All tests use an isolated install directory; cleanup is automatic.
    """

    @pytest.mark.timeout(600)
    def test_install_via_controller_thread(
        self, python_installer_env, check_environment, isolated_install_dir
    ):
        """
        T01 — Install Python via the controller thread.

        Verifies that:
        - Controller thread completes without hanging
        - status is True after join()
        - installed_executable points to a real python.exe
        """
        ctrl = _make_controller(python_installer_env, isolated_install_dir)
        ctrl.start()
        ctrl.join(timeout=python_installer_env['timeout'])

        assert ctrl.status is True, (
            f"Install failed — controller status={ctrl.status}, "
            f"error_count={ctrl.error_count}"
        )
        assert ctrl.installed_executable, (
            "installed_executable is empty after successful install"
        )
        assert Path(ctrl.installed_executable).is_file(), (
            f"python.exe not found at '{ctrl.installed_executable}'"
        )

        # Cleanup — uninstall before tmp_path is wiped
        ctrl.uninstall()

    @pytest.mark.timeout(600)
    def test_install_and_verify_is_installed(
        self, python_installer_env, check_environment, isolated_install_dir
    ):
        """
        T02 — After install, is_installed() returns True.
        After uninstall, is_installed() returns False.
        """
        ctrl = _make_controller(python_installer_env, isolated_install_dir)

        assert ctrl.is_installed() is False, (
            "is_installed() should be False before install"
        )

        ctrl.install()   # synchronous / blocking

        assert ctrl.is_installed() is True, (
            "is_installed() should be True after install"
        )

        # Cleanup
        ctrl.uninstall()

        assert ctrl.is_installed() is False, (
            "is_installed() should be False after uninstall"
        )

    @pytest.mark.timeout(600)
    def test_install_then_uninstall_via_thread(
        self, python_installer_env, check_environment, isolated_install_dir
    ):
        """
        T03 — Controller with uninstall_after_test=True installs then uninstalls.
        """
        ctrl = _make_controller(
            python_installer_env,
            isolated_install_dir,
            uninstall_after_test=True,
        )
        ctrl.start()
        ctrl.join(timeout=python_installer_env['timeout'])

        assert ctrl.status is True, (
            f"Install+uninstall cycle failed — status={ctrl.status}"
        )
        # After uninstall, the exe should be gone
        assert ctrl.is_installed() is False, (
            "python.exe still present after uninstall_after_test=True"
        )

    @pytest.mark.timeout(30)
    def test_stop_signal_terminates_cleanly(
        self, python_installer_env, check_environment, isolated_install_dir
    ):
        """
        T04 — stop() before the thread does real work returns a defined status.

        This test does NOT trigger an actual install; it fires stop() so quickly
        that _execute_operation returns before calling the process manager.
        """
        ctrl = _make_controller(python_installer_env, isolated_install_dir)
        ctrl.stop()          # set stop_event before start()
        ctrl.start()
        ctrl.join(timeout=15)

        # With stop_event pre-set, _execute_operation returns immediately → status=True
        assert ctrl.status is True


@pytest.mark.integration
@pytest.mark.requires_python_installer
@pytest.mark.slow
class TestPythonInstallerProcessManagerIntegration:
    """Direct PythonInstallerProcessManager tests (lower-level than controller)."""

    @pytest.mark.timeout(600)
    def test_full_install_uninstall_cycle(
        self, python_installer_env, check_environment, isolated_install_dir
    ):
        """
        T05 — ProcessManager install → verify → uninstall.
        """
        pm = _make_process_manager(python_installer_env, isolated_install_dir)

        assert pm.is_installed() is False

        pm.install()

        assert pm.is_installed() is True
        exe = pm.get_executable_path()
        assert exe and Path(exe).is_file(), (
            f"python.exe not found at '{exe}'"
        )

        pm.uninstall()

        assert pm.is_installed() is False

    @pytest.mark.timeout(30)
    def test_version_resolution(
        self, python_installer_env, check_environment, isolated_install_dir
    ):
        """
        T06 — _resolve_full_version converts '3.11' → '3.11.0' (or latest patch).
        """
        pm = _make_process_manager(python_installer_env, isolated_install_dir)
        pm._resolve_full_version()

        parts = pm.full_version.split('.')
        assert len(parts) == 3, (
            f"full_version should be MAJOR.MINOR.PATCH, got '{pm.full_version}'"
        )
        assert parts[0] == python_installer_env['version'].split('.')[0]
        assert parts[1] == python_installer_env['version'].split('.')[1]
