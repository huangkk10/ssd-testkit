"""
Test configuration for STC-2557 ADK S3/S4/S5 test

This conftest.py provides test-project-specific configuration.
Common configuration classes and fixtures are inherited from tests/integration/conftest.py
"""

import pytest
from pathlib import Path

# Import shared TestCaseConfiguration from parent conftest
from tests.integration.conftest import TestCaseConfiguration


@pytest.fixture(scope="session")
def testcase_config():
    """Provide TestCaseConfiguration for STC-2557."""
    return TestCaseConfiguration(Path(__file__).parent)

# Absolute path to the reboot state file (relative paths are unreliable at
# collection time because os.chdir() hasn't run yet).
_CASE_DIR = Path(__file__).parent
_STATE_FILE = _CASE_DIR / "testlog" / "reboot_state.json"


def pytest_collection_finish(session):
    """
    Auto-clear the reboot state file when test_01_precondition is NOT
    in the collected tests.

    This lets developers run individual post-reboot steps (e.g. test_06,
    test_07) directly from VS Code without the session appearing as
    POST-REBOOT (recovery).

    The cleanup is skipped when:
    - test_01 IS collected  → full run, state managed by the test itself.
    - No STC-2557 tests collected at all → nothing to do.
    - State file doesn't exist → already clean.
    """
    stc2557_items = [
        item for item in session.items
        if 'stc2557_adk_s3s4s5' in item.nodeid
    ]
    if not stc2557_items:
        return  # not our test

    has_test01 = any('test_01_precondition' in item.nodeid for item in stc2557_items)
    if has_test01:
        return  # full run — let test_01 manage the state file

    # Post-reboot tests (after S4 hibernate / S5 cold reboot): test_07, test_08
    _POST_REBOOT_TESTS = {
        'test_06_wait_results',
        'test_07_verify',
    }
    collected_names = {item.name for item in stc2557_items}

    if collected_names.issubset(_POST_REBOOT_TESTS):
        reboot_count = 1
    else:
        reboot_count = None  # not a recognisable post-reboot partial run

    if reboot_count is not None:
        if not _STATE_FILE.exists():
            import json as _json
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _STATE_FILE.write_text(
                _json.dumps({
                    "is_recovering": True,
                    "reboot_count": reboot_count,
                    "current_cycle": 1,
                    "total_cycles": 1,
                    "last_reboot_timestamp": "synthetic",
                }, indent=2),
                encoding='utf-8',
            )
            print(
                f"\n[STC-2557 conftest] Created synthetic reboot state "
                f"(reboot_count={reboot_count}) for post-reboot partial run: {_STATE_FILE}"
            )
        return  # post-reboot partial run — keep state file

    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
        print(f"\n[STC-2557 conftest] Removed reboot state for partial run: {_STATE_FILE}")


@pytest.fixture(scope="session")
def testcase_config():
    """
    Provide test case configuration as a fixture.

    Automatically infers configuration from directory structure.
    Uses the shared TestCaseConfiguration class from tests/integration/conftest.py

    Usage in test:
        def setup_test_class(self, request, testcase_config, runcard_params):
            ...
            cls._init_runcard(runcard_params)
    """
    case_root_dir = Path(__file__).parent
    config = TestCaseConfiguration(case_root_dir)
    return config
