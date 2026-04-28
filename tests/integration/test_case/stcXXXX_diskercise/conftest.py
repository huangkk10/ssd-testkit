"""
Test configuration for STC-XXXX Diskercise
"""
import pytest
from pathlib import Path
from tests.integration.conftest import TestCaseConfiguration


@pytest.fixture(scope="session")
def testcase_config():
    """Provide TestCaseConfiguration for STC-XXXX Diskercise."""
    return TestCaseConfiguration(Path(__file__).parent)
