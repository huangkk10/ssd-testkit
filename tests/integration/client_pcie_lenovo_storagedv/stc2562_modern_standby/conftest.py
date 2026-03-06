"""
Test configuration for STC-2562 Modern Standby test

This conftest.py provides test-project-specific configuration.
Common configuration classes and fixtures are inherited from tests/integration/conftest.py
"""

import pytest
from pathlib import Path

# Import shared TestCaseConfiguration from parent conftest
from tests.integration.conftest import TestCaseConfiguration

# Absolute path to the reboot state file (relative paths are unreliable at
# collection time because os.chdir() hasn't run yet).
_CASE_DIR = Path(__file__).parent
_STATE_FILE = _CASE_DIR / "testlog" / "reboot_state.json"


def pytest_collection_finish(session):
    """
    Auto-clear the reboot state file when test_01_precondition is NOT
    in the collected tests.

    This lets developers run any individual step (e.g. test_05) directly
    from VS Code without the session appearing as POST-REBOOT (recovery),
    which would skip all pre-reboot steps.

    The cleanup is skipped when:
    - test_01 IS collected  → full run, state managed by the test itself.
    - No STC-2562 tests collected at all → nothing to do.
    - State file doesn't exist → already clean.
    """
    stc2562_items = [
        item for item in session.items
        if 'stc2562_modern_standby' in item.nodeid
    ]
    if not stc2562_items:
        return  # not our test

    has_test01 = any('test_01_precondition' in item.nodeid for item in stc2562_items)
    if has_test01:
        return  # full run — let test_01 manage the state file

    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
        print(f"\n[STC-2562 conftest] Removed reboot state for partial run: {_STATE_FILE}")


@pytest.fixture(scope="session")
def testcase_config():
    """
    Provide test case configuration as a fixture.

    Automatically infers configuration from directory structure.
    Uses the shared TestCaseConfiguration class from tests/integration/conftest.py

    Usage in test:
        def test_something(testcase_config):
            print(testcase_config.case_id)  # "STC-2562"
    """
    case_root_dir = Path(__file__).parent
    config = TestCaseConfiguration(case_root_dir)

    # SmiCli2.exe is located inside SmiWinTools (not the default bin/SmiCli/ path).
    # Override so RunCard.generate_dut_info() can collect DUT info correctly.
    config.smicli_executable = case_root_dir / "bin/SmiWinTools/bin/x64/SmiCli2.exe"

    return config
