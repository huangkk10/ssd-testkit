"""
Test configuration for STC-1067 WinPVT Standby Critical
"""
import pytest
from pathlib import Path
from tests.integration.conftest import TestCaseConfiguration


@pytest.fixture(scope="session")
def testcase_config():
    """Provide TestCaseConfiguration for STC-1067."""
    return TestCaseConfiguration(Path(__file__).parent)
