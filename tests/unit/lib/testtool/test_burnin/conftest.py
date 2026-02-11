"""
Pytest configuration and fixtures for BurnIN unit tests.
"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file path (not created yet)."""
    return os.path.join(temp_dir, 'test_file.txt')


@pytest.fixture
def temp_script_path(temp_dir):
    """Create a temporary script file path."""
    return os.path.join(temp_dir, 'test_script.bits')


@pytest.fixture
def temp_config_path(temp_dir):
    """Create a temporary config file path."""
    return os.path.join(temp_dir, 'test_config.bitcfg')


@pytest.fixture
def temp_log_path(temp_dir):
    """Create a temporary log file path."""
    return os.path.join(temp_dir, 'test.log')


@pytest.fixture
def sample_config():
    """Sample valid configuration dictionary."""
    return {
        'test_duration_minutes': 60,
        'test_drive_letter': 'D',
        'timeout_seconds': 3600,
        'check_interval_seconds': 2,
    }
