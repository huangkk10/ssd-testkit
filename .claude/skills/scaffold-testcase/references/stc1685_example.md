````markdown
# STC-1685 — Complete Worked Example

This is the canonical example for integration test case structure.
**Source**: `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/`

---

## Test Spec

```
STC ID:       STC-1685
Client:       client_pcie_lenovo_storagedv
Short name:   stc1685_burnin
Description:  BurnIN install + 24h disk stress test + concurrent SMART monitoring
Tools:        BurnInController, CDIController, SmartCheckController, DiskPrd
Steps:        6
Concurrent:   Yes (step 5: BurnIN + SmartCheck in parallel threads)
Reboot:       No
```

---

## Directory Structure

```
stc1685_burnin/
├── Config/
│   └── Config.json
├── bin/
│   ├── BurnIn/
│   │   ├── bitwindows.exe
│   │   ├── key.dat
│   │   └── Configs/
│   │       ├── BurnInScript.bits
│   │       └── BurnInScript.bitcfg
│   └── SmiWinTools/
│       └── SmartCheck.bat
├── conftest.py
├── test_main.py
├── README.md
└── __init__.py
```

---

## conftest.py

```python
"""
Test configuration for STC-1685 BurnIN test
"""
import pytest
from pathlib import Path
from tests.integration.conftest import TestCaseConfiguration

@pytest.fixture(scope="session")
def testcase_config():
    case_root_dir = Path(__file__).parent
    return TestCaseConfiguration(case_root_dir)
```

---

## Config/Config.json (key sections)

```json
{
  "test_name": "STC-1685",
  "description": "H2test Write Half + BurnIN Test (Pytest Framework)",
  "log_path": "./log/STC-1685",

  "burnin": {
    "installer": "./bin/BurnIn/bitwindows.exe",
    "license_path": "./bin/BurnIn/key.dat",
    "install_path": "C:\\Program Files\\BurnInTest",
    "script_path": "./bin/BurnIn/Configs/BurnInScript.bits",
    "config_file_path": "./bin/BurnIn/Configs/BurnInScript.bitcfg",
    "log_path": "./testlog/Burnin.log",
    "screenshot_path": "./testlog/Burnin.png",
    "timeout_minutes": 5,
    "test_duration_minutes": 1,
    "test_drive_letter": "D"
  },

  "smartcheck": {
    "bat_path": "./bin/SmiWinTools/SmartCheck.bat",
    "output_dir": "./testlog/SmartLog",
    "total_time": 10080,
    "check_interval": 3,
    "timeout": 120
  },

  "cdi": {
    "ExePath": "./bin/CrystalDiskInfo/DiskInfo64.exe",
    "LogPath": "./testlog/CDILog",
    "ScreenShotDriveLetter": "C:"
  }
}
```

---

## Test Steps Summary

| Step | Method | Description |
|------|--------|-------------|
| 1 | `test_01_precondition` | Remove old BurnIN install, clean logs, create log dirs |
| 2 | `test_02_install_burnin` | Install BurnIN via `BurnInController.install()` |
| 3 | `test_03_partition_disk` | Delete D: → extend C: → shrink C: → create D: (NTFS 10GB 4K) |
| 4 | `test_04_cdi_before` | CDI snapshot → CDI_before.txt/.json/.png |
| 5 | `test_05_burnin_smartcheck` | **Concurrent**: BurnIN thread + SmartCheck thread, monitoring loop |
| 6 | `test_06_cdi_after` | CDI snapshot → CDI_after + compare SMART (no-increase + zero-error) |

---

## Class-level Markers

```python
@pytest.mark.client_lenovo
@pytest.mark.interface_pcie
@pytest.mark.project_storagedv
@pytest.mark.feature_burnin
@pytest.mark.slow
class TestSTC1685BurnIN(BaseTestCase):
    ...
```

---

## setup_test_class Fixture (Full)

```python
@pytest.fixture(scope="class", autouse=True)
def setup_test_class(self, request, testcase_config, runcard_params):
    cls = request.cls
    cls.testcase_config = testcase_config
    cls.original_cwd = os.getcwd()

    try:
        from path_manager import path_manager
        test_dir = path_manager.app_dir
    except ImportError:
        test_dir = Path(__file__).parent

    os.chdir(test_dir)
    logConfig()

    cls.config = testcase_config.tool_config
    cls.bin_path = testcase_config.bin_directory

    logger.info(f"Working directory: {test_dir}")
    logger.info(f"Test case: {testcase_config.case_id}")

    cls.runcard = None
    try:
        cls.runcard = RC.Runcard(**runcard_params['initialization'])
        cls.runcard.start_test(**runcard_params['start_params'])
        logger.info("[RunCard] Started")
    except Exception as e:
        logger.error(f"[RunCard] Init failed: {e}")

    yield

    if cls.runcard:
        try:
            failed = request.session.testsfailed > 0
            cls.runcard.end_test(
                RC.TestResult.FAIL.value if failed else RC.TestResult.PASS.value
            )
        except Exception as e:
            logger.error(f"[RunCard] End failed: {e}")

    os.chdir(cls.original_cwd)
```

---

## test_05 — Concurrent BurnIN + SmartCheck (Full Pattern)

```python
@pytest.mark.order(5)
@step(5, "Run BurnIN and SmartCheck concurrently")
def test_05_burnin_smartcheck(self):
    # Initialize both controllers
    smartcheck_controller = SmartCheckController.from_config_dict(
        self.config.get('smartcheck', {}))
    burnin_controller = BurnInController.from_config_dict(self.config['burnin'])
    burnin_controller.load_config_from_json('./Config/Config.json', config_key='burnin')

    # Start SmartCheck first, then BurnIN
    smartcheck_controller.start()
    time.sleep(2)
    burnin_controller.start()

    timeout_seconds = burnin_controller.timeout_minutes * 60
    start_time = time.time()
    timeout_hit = False

    try:
        while True:
            if smartcheck_controller.status is False:
                break
            if burnin_controller.status is False:
                break
            if not burnin_controller.is_alive():
                time.sleep(0.5)
                if burnin_controller.status is True:
                    break
            if not burnin_controller.is_alive() and not smartcheck_controller.is_alive():
                break
            if time.time() - start_time > timeout_seconds:
                timeout_hit = True
                break
            time.sleep(1)
    finally:
        burnin_controller.stop()
        smartcheck_controller.stop()
        burnin_controller.join(timeout=10)
        smartcheck_controller.join(timeout=10)

    if timeout_hit:
        pytest.fail("Test timeout")
    if burnin_controller.status is False:
        pytest.fail(f"BurnIN failed ({burnin_controller.error_count} errors)")
    if smartcheck_controller.status is False:
        pytest.fail("SmartCheck detected SMART errors")
```

---

## Reference Files

- `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/test_main.py`
- `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/conftest.py`
- `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/Config/Config.json`
- `tests/integration/conftest.py`
````
