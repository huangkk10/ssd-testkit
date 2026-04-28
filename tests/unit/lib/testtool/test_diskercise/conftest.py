"""
Pytest configuration and fixtures for Diskercise unit tests.
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
    """Temporary log directory path."""
    return os.path.join(temp_dir, 'diskercise_log')


@pytest.fixture
def sample_config():
    """Minimal valid configuration dictionary."""
    return {
        'thread_count': 4,
        'file_size_mb': 100,
        'test_duration_minutes': 15,
    }
