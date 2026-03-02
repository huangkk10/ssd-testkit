"""
Pytest configuration and fixtures for PwrTest unit tests.
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
    return os.path.join(temp_dir, 'pwrtestlog.log')


@pytest.fixture
def sample_config():
    """Minimal valid configuration dictionary for PwrTestController init."""
    return {
        'executable_path': './tests/unit/lib/testtool/bin/SmiWinTools/bin/x64/pwrtest/win11/25H2/pwrtest.exe',
        'cycle_count':        1,
        'delay_seconds':      5,
        'wake_after_seconds': 30,
        'timeout_seconds':    120,
    }


# ---------------------------------------------------------------------------
# Fixture log content (mirrors real pwrtestlog.log format)
# ---------------------------------------------------------------------------

PASS_LOG = """\
Start: PwrTest

SYSTEM_POWER_CAPABILITIES 

    SystemS3StateSupported = 1 

No.1 of 1 Transition -- TargetState: S3

  TargetState:       S3

  EffectiveState:    S3

  SleepTimeMs:       1134    

  BiosInitTimeMs:    3242    

  DriverWakeTimeMs:  442     

  Transition StartTime: 03/02/2026 12:57:38::597

  Transition EndTime:   03/02/2026 12:58:43::956

No.1 of 1 Transition -- Complete

End: Pass, PwrTest, (null)

"""

FAIL_LOG = """\
Start: PwrTest

No.1 of 2 Transition -- TargetState: S3

  TargetState:       S3

  EffectiveState:    S3

  SleepTimeMs:       900    

  BiosInitTimeMs:    2000    

  DriverWakeTimeMs:  300     

  Transition StartTime: 03/02/2026 13:00:00::000

  Transition EndTime:   03/02/2026 13:00:30::000

No.1 of 2 Transition -- Complete

No.2 of 2 Transition -- TargetState: S3

  TargetState:       S3

End: Fail, PwrTest, Resume failed

"""


@pytest.fixture
def pass_log_file(temp_dir):
    """Write a minimal PASS log file and return its path."""
    path = os.path.join(temp_dir, 'pwrtestlog.log')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(PASS_LOG)
    return path


@pytest.fixture
def fail_log_file(temp_dir):
    """Write a minimal FAIL log file and return its path."""
    path = os.path.join(temp_dir, 'pwrtestlog.log')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(FAIL_LOG)
    return path
