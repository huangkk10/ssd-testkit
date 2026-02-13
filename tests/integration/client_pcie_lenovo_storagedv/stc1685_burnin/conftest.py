"""
Test configuration for STC-1685 BurnIN test

This conftest.py provides test-project-specific configuration.
Common configuration classes and fixtures are inherited from tests/integration/conftest.py
"""

import pytest
from pathlib import Path

# Import shared TestCaseConfiguration from parent conftest
from tests.integration.conftest import TestCaseConfiguration


@pytest.fixture(scope="session")
def testcase_config():
    """
    Provide test case configuration as a fixture.
    
    Automatically infers configuration from directory structure.
    Uses the shared TestCaseConfiguration class from tests/integration/conftest.py
    
    Usage in test:
        def test_something(testcase_config):
            print(testcase_config.case_id)  # "STC-1685"
            print(testcase_config.case_version)  # "1.0.0"
    """
    case_root_dir = Path(__file__).parent
    config = TestCaseConfiguration(case_root_dir)
    return config
