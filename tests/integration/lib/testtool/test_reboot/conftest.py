"""
Integration test fixtures for OsRebootController.

These tests issue a *real* ``shutdown /r`` command which will reboot the machine.
They are guarded by a safety environment variable:

    ENABLE_REBOOT_INTEGRATION_TEST=1

The guard is implemented as a session-scoped fixture (``check_environment``).
Tests that require the guard list it as a parameter.  Tests that do NOT cause
a real reboot (e.g. recovery-detection tests) omit it so they always run.

Usage:
    set ENABLE_REBOOT_INTEGRATION_TEST=1
    python -m pytest tests/integration/lib/testtool/test_reboot/ -v
"""
import os
import pytest


@pytest.fixture(scope="session")
def check_environment():
    """
    Session-scoped guard fixture.

    Skip if ``ENABLE_REBOOT_INTEGRATION_TEST`` is not set to ``1``.
    Tests request this fixture by name; collection always succeeds so that
    VS Code Test Explorer can display all tests.  Skipping happens at
    execution time, not at collection time.
    """
    enabled = os.environ.get('ENABLE_REBOOT_INTEGRATION_TEST', '0')
    if enabled != '1':
        pytest.skip(
            "OsReboot integration tests are disabled. "
            "Set ENABLE_REBOOT_INTEGRATION_TEST=1 to enable."
        )


@pytest.fixture
def reboot_log_dir(tmp_path):
    """Provide an isolated log directory for each test."""
    log_dir = tmp_path / 'reboot_integration'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def reboot_state_file(reboot_log_dir):
    """Return path to the per-test state file."""
    return str(reboot_log_dir / 'reboot_state.json')
