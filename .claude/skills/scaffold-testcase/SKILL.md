````skill
---
name: scaffold-testcase
description: Scaffold a new integration test case under tests/integration/<client>/<stcXXXX_name>/ using STC-1685 as the standard template. Use when user asks to create a new test case, add an integration test, write a test script for a specific STC, or mentions 建 test case, 新增測試, 寫測試腳本, 建立 STC, or similar. Also provides guidance on test step ordering, pytest markers, RunCard integration, concurrent controller usage, and Config.json design.
---

# Scaffold Integration Test Case Skill

Generate a new integration test case under `tests/integration/<client>/<stcXXXX_name>/`
following the standard architecture defined by `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/`.

---

## Standard Directory Structure

```
tests/integration/<client>/<stcXXXX_name>/
├── Config/
│   └── Config.json           # Tool path + execution params
├── bin/                      # Test executables (committed or pre-placed)
│   └── <ToolDir>/
│       └── <executable>
├── conftest.py               # testcase_config fixture (local)
├── test_main.py              # Main test class (all steps)
├── README.md                 # Test overview and run instructions
└── __init__.py               # Empty, required for pytest discovery
```

### Client / STC naming conventions

| Part | Rule | Example |
|------|------|---------|
| `<client>` | `client_<interface>_<brand>_<project>` | `client_pcie_lenovo_storagedv` |
| `<stcXXXX_name>` | `stc<id>_<short_description>` (lowercase, underscores) | `stc1685_burnin` |

---

## Workflow

### Step 1 — Gather Test Spec

Ask the user (or parse from description):

| Field | Question |
|-------|---------|
| `stc_id` | STC 編號？（如 `1685`） |
| `short_name` | 測試簡稱（snake_case）？（如 `burnin`） |
| `client` | 客戶/平台目錄名稱？（如 `client_pcie_lenovo_storagedv`） |
| `description` | 這個測試做什麼？（一句話說明） |
| `tools_used` | 用到哪些 lib/testtool 的 Controller？（如 BurnIn, CDI, SmartCheck） |
| `steps` | 有哪些測試步驟？（step 1, 2, 3...） |
| `has_concurrent` | 是否有並行測試步驟？（如 BurnIN + SmartCheck 同時跑） |
| `needs_reboot` | 測試中是否需要重開機？ |

### Step 2 — Generate Files

Generate each file in this order:

1. `__init__.py` — empty
2. `Config/Config.json` — tool paths + execution parameters
3. `conftest.py` — `testcase_config` session fixture
4. `test_main.py` — main test class with all steps
5. `README.md` — overview, structure, run instructions

**For complete file templates**, see `references/testcase_templates.md`
**For a complete worked example**, see `references/stc1685_example.md`
**For structure rules**, see `references/testcase_structure.md`

### Step 3 — Verify

```powershell
# Check for syntax errors
python -m py_compile tests/integration/<client>/<stcXXXX_name>/test_main.py

# Run (development, no real tools needed for collection test)
python -m pytest tests/integration/<client>/<stcXXXX_name>/test_main.py --collect-only

# Full run (requires real executables in bin/)
python -m pytest tests/integration/<client>/<stcXXXX_name>/test_main.py -v -s
```

---

## Key Architecture Rules

### Test Class

- Always inherit from `framework.base_test.BaseTestCase`
- Decorate class with relevant `@pytest.mark.*` labels (see Markers section)
- Use a **class-level** `setup_test_class` fixture (`scope="class", autouse=True`) for:
  - Loading `testcase_config` and `runcard_params`
  - Changing working directory (`os.chdir`)
  - Initializing logger (`logConfig()`)
  - Starting and ending **RunCard**
- Use `@pytest.mark.order(N)` + `@step(N, "description")` on every test method

### Test Method Naming

```
test_01_precondition
test_02_<first_tool_action>
test_03_<next_action>
...
```

- Zero-padded two-digit numbers ensure correct ordering
- Each test method has a single responsibility

### setup_test_class Fixture Pattern

```python
@pytest.fixture(scope="class", autouse=True)
def setup_test_class(self, request, testcase_config, runcard_params):
    cls = request.cls
    cls.testcase_config = testcase_config
    cls.original_cwd = os.getcwd()

    # Resolve test directory (packaged vs development)
    try:
        from path_manager import path_manager
        test_dir = path_manager.app_dir
    except ImportError:
        test_dir = Path(__file__).parent
    os.chdir(test_dir)

    logConfig()

    cls.config = testcase_config.tool_config
    cls.bin_path = testcase_config.bin_directory

    # RunCard start
    cls.runcard = None
    try:
        cls.runcard = RC.Runcard(**runcard_params['initialization'])
        cls.runcard.start_test(**runcard_params['start_params'])
    except Exception as e:
        logger.error(f"[RunCard] Initialization failed - {e}")

    yield

    # RunCard end
    if cls.runcard:
        failed = request.session.testsfailed > 0
        result = RC.TestResult.FAIL.value if failed else RC.TestResult.PASS.value
        cls.runcard.end_test(result)

    os.chdir(cls.original_cwd)
```

### conftest.py Pattern

```python
import pytest
from pathlib import Path
from tests.integration.conftest import TestCaseConfiguration

@pytest.fixture(scope="session")
def testcase_config():
    return TestCaseConfiguration(Path(__file__).parent)
```

The shared `runcard_params` fixture is defined in `tests/integration/conftest.py`
and is automatically available to all sub-test conftest.py files.

---

## Pytest Markers

Apply markers on the test class level. Use `@pytest.mark.<marker>` for:

| Category | Marker examples |
|----------|----------------|
| Client | `@pytest.mark.client_lenovo`, `@pytest.mark.client_samsung` |
| Interface | `@pytest.mark.interface_pcie`, `@pytest.mark.interface_sata` |
| Project | `@pytest.mark.project_storagedv`, `@pytest.mark.project_burnin` |
| Feature | `@pytest.mark.feature_burnin`, `@pytest.mark.feature_smart` |
| Speed | `@pytest.mark.slow` (for tests > 30 min) |

Register new markers in `pytest.ini` under `markers =`. The project uses `--strict-markers`.

---

## Config.json Design Principles

- **Only path/environment params** belong in Config.json (exe path, log dir, drive letter)
- **Execution params** (duration, cycle count, intervals) also go in Config.json as defaults
- Each tool tool gets its own JSON key (e.g., `"burnin"`, `"smartcheck"`, `"cdi"`)
- Keep keys consistent with a controller's `from_config_dict()` expectations

**Standard Config.json skeleton:**
```json
{
  "test_name": "STC-XXXX",
  "description": "Short description",
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
  }
}
```

---

## Controller Usage Pattern

All `lib/testtool` controllers follow the same threading interface:

```python
# 1. Instantiate
ctrl = SomeController.from_config_dict(self.config['<key>'])

# 2. (Optional) override specific params
ctrl.set_config(log_path='./testlog/run1.log')

# 3. Run in thread
ctrl.start()

# 4. Wait for completion
ctrl.join(timeout=ctrl.timeout * 60)

# 5. Check result
if ctrl.status is not True:
    pytest.fail("Controller failed")
```

**`status` values:**
- `None` — still running
- `True` — passed
- `False` — failed

---

## Concurrent Test Pattern

Use when two controllers must run in parallel (e.g., BurnIN + SmartCheck):

```python
# Start both threads
smartcheck.start()
time.sleep(2)
burnin.start()

timeout_seconds = burnin.timeout_minutes * 60
start_time = time.time()
timeout_hit = False

try:
    while True:
        # Cross-stop on failure
        if smartcheck.status is False:
            break
        if burnin.status is False:
            break
        # Primary thread finished successfully
        if not burnin.is_alive() and burnin.status is True:
            break
        # Timeout guard
        if time.time() - start_time > timeout_seconds:
            timeout_hit = True
            break
        time.sleep(1)
finally:
    # Always stop both, even on exception
    burnin.stop()
    smartcheck.stop()
    burnin.join(timeout=10)
    smartcheck.join(timeout=10)

# Evaluate result
if timeout_hit:
    pytest.fail("Test timeout")
if burnin.status is False:
    pytest.fail(f"BurnIN failed ({burnin.error_count} errors)")
if smartcheck.status is False:
    pytest.fail("SmartCheck detected SMART errors")
```

---

## CDI Before/After SMART Comparison Pattern

Standard pattern for capturing SMART baseline before test and comparing after:

```python
# Before test (test_XX_cdi_before):
cdi = CDIController()
cdi.load_config_from_json('./Config/Config.json', config_key='cdi')
cdi.set_config(
    diskinfo_txt_name='CDI_before.txt',
    diskinfo_json_name='CDI_before.json',
    diskinfo_png_name='CDI_before.png',
)
cdi.start()
cdi.join(timeout=120)
assert cdi.status is True

# After test (test_XX_cdi_after):
cdi = CDIController()
cdi.load_config_from_json('./Config/Config.json', config_key='cdi')
cdi.set_config(
    diskinfo_txt_name='CDI_after.txt',
    diskinfo_json_name='CDI_after.json',
    diskinfo_png_name='CDI_after.png',
)
cdi.start()
cdi.join(timeout=120)
assert cdi.status is True

# Compare: no-increase check (e.g., Unsafe Shutdowns)
cdi.set_config(diskinfo_json_name='.json')
result, msg = cdi.compare_smart_value_no_increase(
    'C:', 'CDI_before', 'CDI_after', ['Unsafe Shutdowns']
)
if not result:
    pytest.fail(f"SMART validation failed: {msg}")

# Compare: must-be-zero check (error counts)
cdi.set_config(diskinfo_json_name='CDI_after.json')
result, msg = cdi.compare_smart_value(
    'C:', '', ['Number of Error Information Log Entries', 'Media and Data Integrity Errors'], 0
)
if not result:
    pytest.fail(f"SMART errors: {msg}")
```

---

## RunCard Integration

RunCard records the test result (PASS/FAIL) at the end of the class fixture:

```python
# Start
cls.runcard = RC.Runcard(**runcard_params['initialization'])
cls.runcard.start_test(**runcard_params['start_params'])

# End (in yield teardown)
failed = request.session.testsfailed > 0
cls.runcard.end_test(
    RC.TestResult.FAIL.value if failed else RC.TestResult.PASS.value
)
```

Always wrap RunCard calls in `try/except`; RunCard failure must not block the test.

---

## Known Test Cases Reference

| STC | Directory | Description |
|-----|-----------|-------------|
| **STC-1685** | `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/` | BurnIN install + 24h disk stress + SMART monitor |

---

## Related Files

- **Canonical test case**: `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/`
- **Shared conftest/fixtures**: `tests/integration/conftest.py` — `TestCaseConfiguration`, `runcard_params`
- **Base test class**: `framework/base_test.py` — `BaseTestCase`
- **Step decorator**: `framework/decorators.py` — `@step(N, "description")`
- **Logger**: `lib/logger.py` — `get_module_logger(__name__)`, `logConfig()`
- **Full STC-1685 example**: `.claude/skills/scaffold-testcase/references/stc1685_example.md`
- **File templates**: `.claude/skills/scaffold-testcase/references/testcase_templates.md`
- **Structure rules**: `.claude/skills/scaffold-testcase/references/testcase_structure.md`

````
