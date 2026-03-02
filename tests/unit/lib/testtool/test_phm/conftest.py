"""
Pytest configuration and fixtures for PHM unit tests.
"""

import os
import tempfile
import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_log_path(temp_dir):
    """Temporary log file path (not created yet)."""
    return os.path.join(temp_dir, 'phm_test.log')


@pytest.fixture
def sample_config():
    """
    Minimal valid PHMConfig override dict.
    All keys must be present in PHMConfig.VALID_PARAMS.
    """
    return {
        'installer_path': './bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe',
        'cycle_count': 5,
        'timeout': 120,
    }


@pytest.fixture
def sample_html_pass():
    """Minimal HTML string that should parse as PASS."""
    return """
    <html>
    <head><title>Powerhouse Mountain Test Report</title></head>
    <body>
    <h1>Powerhouse Mountain Test Report</h1>
    <p>Start Time: 2026-03-02 10:00:00</p>
    <p>End Time: 2026-03-02 11:00:00</p>
    <p>Total Cycles: 10</p>
    <p>Completed Cycles: 10</p>
    <p>Test Result: PASS</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_fail():
    """Minimal HTML string that should parse as FAIL with errors."""
    return """
    <html>
    <head><title>Powerhouse Mountain Test Report</title></head>
    <body>
    <h1>Powerhouse Mountain Test Report</h1>
    <p>Start Time: 2026-03-02 10:00:00</p>
    <p>End Time: 2026-03-02 10:30:00</p>
    <p>Total Cycles: 10</p>
    <p>Completed Cycles: 3</p>
    <p>Test Result: FAIL</p>
    <p>Error: S0ix entry failed on cycle 4</p>
    <p>Error: Power loss detected unexpectedly</p>
    </body>
    </html>
    """


@pytest.fixture
def html_pass_file(temp_dir, sample_html_pass):
    """Write sample PASS HTML to a temp file, return path."""
    path = os.path.join(temp_dir, 'report_pass.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(sample_html_pass)
    return path


@pytest.fixture
def html_fail_file(temp_dir, sample_html_fail):
    """Write sample FAIL HTML to a temp file, return path."""
    path = os.path.join(temp_dir, 'report_fail.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(sample_html_fail)
    return path
