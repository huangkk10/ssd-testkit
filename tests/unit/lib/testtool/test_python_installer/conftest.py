"""
Pytest configuration and shared fixtures for PythonInstaller unit tests.
"""

import pytest
import tempfile
import os


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_log_path(temp_dir):
    """Temporary log file path (not created yet)."""
    return os.path.join(temp_dir, 'python_installer.log')


@pytest.fixture
def sample_config():
    """Minimal valid configuration dictionary (Python 3.11, amd64)."""
    return {
        'version': '3.11',
        'architecture': 'amd64',
        'timeout_seconds': 60,
    }


@pytest.fixture
def sample_config_with_path(temp_dir):
    """Valid configuration with explicit install_path."""
    return {
        'version': '3.11',
        'architecture': 'amd64',
        'install_path': temp_dir,
        'timeout_seconds': 60,
    }
