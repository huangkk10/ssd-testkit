````markdown
# Test Case File Templates

---

## 1. `__init__.py`

```python
```
*(empty file)*

---

## 2. `conftest.py`

```python
"""
Test configuration for <STC-XXXX> <description>
"""
import pytest
from pathlib import Path
from tests.integration.conftest import TestCaseConfiguration


@pytest.fixture(scope="session")
def testcase_config():
    """
    Provide test case configuration as a fixture.
    Uses TestCaseConfiguration to auto-infer case_id from directory name.
    """
    return TestCaseConfiguration(Path(__file__).parent)
```

---

## 3. `Config/Config.json`

```json
{
  "test_name": "STC-XXXX",
  "description": "<One-line description>",
  "log_path": "./log/STC-XXXX",

  "<tool1>": {
    "ExePath": "./bin/<ToolDir>/<executable>",
    "LogPath": "./testlog/<ToolLog>",
    "timeout": 120
  },

  "<tool2>": {
    "installer": "./bin/<ToolDir>/setup.exe",
    "install_path": "C:\\Program Files\\<Tool>",
    "log_path": "./testlog/<Tool>.log",
    "timeout_minutes": 60,
    "test_duration_minutes": 30
  },

  "cdi": {
    "ExePath": "./bin/CrystalDiskInfo/DiskInfo64.exe",
    "LogPath": "./testlog/CDILog",
    "ScreenShotDriveLetter": "C:"
  }
}
```

---

## 4. `test_main.py` (Full skeleton)

```python
"""
STC-XXXX: <Test Name> (Pytest Framework)

<One paragraph description>

Test Flow:
1. Precondition - Basic setup
2. <Step 2 description>
3. <Step 3 description>
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
import time
import pytest
from framework.base_test import BaseTestCase
from framework.decorators import step
from framework.test_utils import cleanup_directory
from lib.testtool import RunCard as RC
from lib.logger import get_module_logger, logConfig

# Import controllers as needed:
# from lib.testtool.burnin import BurnInController
# from lib.testtool.cdi import CDIController
# from lib.testtool.smartcheck import SmartCheckController

logger = get_module_logger(__name__)


@pytest.mark.client_<brand>
@pytest.mark.interface_<iface>
@pytest.mark.project_<project>
@pytest.mark.feature_<feature>
# @pytest.mark.slow  # uncomment if test > 30 min
class TestSTC<XXXX><Name>(BaseTestCase):
    """
    STC-XXXX: <Test Name> for <Client>
    """

    # ─────────────────────────────────────────────────────────
    # Class fixture: init + RunCard + teardown
    # ─────────────────────────────────────────────────────────

    @pytest.fixture(scope="class", autouse=True)
    def setup_test_class(self, request, testcase_config, runcard_params):
        """Load configuration and initialize (runs before all tests in class)"""
        cls = request.cls
        cls.testcase_config = testcase_config
        cls.original_cwd = os.getcwd()

        # Resolve test directory (packaged vs development)
        try:
            from path_manager import path_manager
            test_dir = path_manager.app_dir
            logger.info(f"[INFO] Packaged environment: {test_dir}")
        except ImportError:
            test_dir = Path(__file__).parent
            logger.info(f"[INFO] Development environment: {test_dir}")

        os.chdir(test_dir)
        logConfig()

        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Test case: {testcase_config.case_id}")
        logger.info(f"Script version: {testcase_config.case_version}")

        cls.config = testcase_config.tool_config
        cls.bin_path = testcase_config.bin_directory

        # RunCard start
        cls.runcard = None
        try:
            cls.runcard = RC.Runcard(**runcard_params['initialization'])
            cls.runcard.start_test(**runcard_params['start_params'])
            logger.info("[RunCard] Test started")
        except Exception as e:
            logger.error(f"[RunCard] Initialization failed - {e} (continuing)")

        yield  # ← tests run here

        # RunCard end
        if cls.runcard:
            try:
                failed = request.session.testsfailed > 0
                if not failed:
                    cls.runcard.end_test(RC.TestResult.PASS.value)
                    logger.info("[RunCard] PASS")
                else:
                    cls.runcard.end_test(
                        RC.TestResult.FAIL.value,
                        f"{request.session.testsfailed} test(s) failed"
                    )
                    logger.info(f"[RunCard] FAIL - {request.session.testsfailed} failed")
            except Exception as e:
                logger.error(f"[RunCard] End failed - {e}")

        logger.info("STC-XXXX Test Completed")
        os.chdir(cls.original_cwd)

    # ─────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────

    def _cleanup_test_logs(self) -> None:
        """
        Remove leftover logs from previous test runs.

        Cleans all tool-specific output directories and log files so each
        full test run starts from a clean state.
        """
        logger.info("[_cleanup_test_logs] Starting test log cleanup")

        # Ensure base testlog dir exists before any cleanup attempts
        Path('./testlog').mkdir(parents=True, exist_ok=True)

        # 0. Reboot state file — remove so next full run starts in PRE-REBOOT phase
        #    (only relevant for tests that use OsRebootController)
        # state_file = Path('./testlog/reboot_state.json')
        # if state_file.exists():
        #     state_file.unlink()
        #     logger.info(f"[_cleanup_test_logs] Removed reboot state file")

        # 1. Tool-specific log directories — add one line per tool used:
        cleanup_directory('./testlog/CDILog', 'CDI log directory', logger)
        # cleanup_directory('./testlog/PwrTestLog', 'PwrTest log directory', logger)
        # cleanup_directory('./testlog/PEPChecker_Log', 'PEPChecker log directory', logger)

        # 2. Single-file outputs — add one block per output file:
        # ss_report = Path(self.config.get('sleepstudy', {}).get('output_path', './testlog/sleepstudy-report.html'))
        # if ss_report.exists():
        #     ss_report.unlink()
        #     logger.info(f"[_cleanup_test_logs] Removed sleepstudy report")

        # 3. Test-specific log directory (log.txt, log.err, etc.)
        log_path = self.config.get('log_path', './log/STC-XXXX')
        cleanup_directory(log_path, 'test log directory', logger)

        # Explicitly remove log.txt and log.err (accumulated across runs)
        log_dir = Path(log_path)
        for log_file in ['log.txt', 'log.err']:
            p = log_dir / log_file
            if p.exists():
                try:
                    p.unlink()
                    logger.info(f"[_cleanup_test_logs] Removed {p}")
                except Exception as exc:
                    logger.warning(f"[_cleanup_test_logs] Could not remove {p}: {exc}")

        logger.info("[_cleanup_test_logs] Cleanup complete")

    # ─────────────────────────────────────────────────────────
    # Test steps
    # ─────────────────────────────────────────────────────────

    @pytest.mark.order(1)
    @step(1, "Setup precondition")
    def test_01_precondition(self):
        """
        Basic setup:
        - Clean up previous test logs
        - Create log directory structure
        """
        logger.info("[TEST_01] Precondition setup started")
        self._cleanup_test_logs()
        logger.info("[TEST_01] Precondition completed")

    @pytest.mark.order(2)
    @step(2, "<Step 2 description>")
    def test_02_<action>(self):
        """
        <Full description of what this step does>

        Steps:
        1. ...
        2. ...
        """
        logger.info("[TEST_02] <Step 2> started")

        # ctrl = SomeController.from_config_dict(self.config['<key>'])
        # ctrl.start()
        # ctrl.join(timeout=ctrl.timeout * 60)
        # if ctrl.status is not True:
        #     pytest.fail("<Step 2> failed")

        logger.info("[TEST_02] <Step 2> completed")

    # Add more steps as needed...


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--log-file=./log/pytest.log",
        "--log-file-level=INFO",
        "--log-file-format=%(asctime)s [%(levelname)s] %(message)s",
        "--log-file-date-format=%Y-%m-%d %H:%M:%S"
    ])
```

---

## 5. `README.md`

```markdown
# STC-XXXX: <Test Name>

## 概述 (Overview)

<One paragraph describing what this test validates>

## 測試流程 (Test Flow)

1. **Precondition** — Clean logs, create directories
2. **<Step 2>** — <Description>
3. **<Step 3>** — <Description>

## 目錄結構 (Directory Structure)

```
stcXXXX_<name>/
├── Config/
│   └── Config.json
├── bin/
│   └── <ToolDir>/
│       └── <executable>
├── test_main.py
└── README.md
```

## 執行測試 (Run Test)

```powershell
cd c:\automation\ssd-testkit

# Collect only (no real tools needed)
pytest tests/integration/<client>/stcXXXX_<name>/test_main.py --collect-only

# Full run
pytest tests/integration/<client>/stcXXXX_<name>/test_main.py -v -s
```

## 設定重點 (Config.json)

| Key | Default | Description |
|-----|---------|-------------|
| `<tool>.timeout_minutes` | 60 | Overall timeout |

## Log 位置

```
./log/STC-XXXX/     ← Test log
./testlog/<Tool>/   ← Tool log
```
```
````
