"""
Shared fixtures for the OsReboot unit test suite.
"""
import pytest


@pytest.fixture
def sample_config():
    """Minimal valid override dict for OsRebootConfig."""
    return {
        'delay_seconds': 5,
        'reboot_count':  2,
        'state_file':    'test_reboot_state.json',
        'abort_on_fail': True,
    }


@pytest.fixture
def temp_state_file(tmp_path):
    """Return a path string inside a temporary directory."""
    return str(tmp_path / 'reboot_state.json')
