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

## Example AI Conversations

以下範例示範如何與 AI 對答，讓它套用此 skill 建立 integration test case。

---

### 範例 A — 最簡短的開場白（讓 AI 主動提問）

**User:**
> 幫我在 tests/integration 底下建立一個新的 STC 測試案例。

**AI 回應（依 Workflow Step 1 逐一確認）：**
> 好的！請提供以下資訊：
> 1. STC 編號？（如 `1720`）
> 2. 測試簡稱？（snake_case，如 `smart_monitor`）
> 3. 客戶/平台目錄？（如 `client_pcie_lenovo_storagedv`，或需要新建？）
> 4. 這個測試做什麼？（一句話說明）
> 5. 用到哪些 testtool Controller？（BurnIn / CDI / SmartCheck / PwrTest / OsReboot...）
> 6. 測試步驟有哪些？（依序列出）
> 7. 是否有並行步驟？是否需要重開機？

---

### 範例 B — 一次提供所有資訊

**User:**
> 幫我建立 STC-1720 的 integration test case。
> - 客戶目錄：`client_pcie_lenovo_storagedv`
> - 簡稱：`power_cycle`
> - 說明：對 SSD 執行 100 次電源循環，並在前後用 CDI 擷取 SMART 數據比對。
> - 用到的工具：PwrTest、CDI
> - 步驟：
>   1. CDI before（取 SMART baseline）
>   2. PwrTest 電源循環 100 次
>   3. CDI after（取 SMART 數據）
>   4. SMART 比對（Unsafe Shutdowns 不能增加，錯誤計數必須為 0）
> - 無並行，無需重開機

**AI 行為：** 直接進入 Step 2，依序產生以下檔案：

```
tests/integration/client_pcie_lenovo_storagedv/stc1720_power_cycle/
├── __init__.py
├── Config/Config.json
├── conftest.py
├── test_main.py
└── README.md
```

---

### 範例 C — 並行測試（BurnIN + SmartCheck 同時跑）

**User:**
> 建立 STC-1730，客戶是 `client_sata_samsung_flagship`，測試名稱 `burnin_smart_concurrent`。
> 步驟：
> 1. CDI before
> 2. BurnIN + SmartCheck 同時跑 8 小時
> 3. CDI after + SMART 比對
> 沒有重開機需求。

**AI 行為：**
- 在 `test_02_burnin_with_smart` 內套用 **Concurrent Test Pattern**（`burnin.start()` / `smartcheck.start()` + cross-stop 迴圈）
- 在 `test_03_cdi_after` 套用 **CDI Before/After SMART Comparison Pattern**
- Config.json 同時包含 `burnin`、`smartcheck`、`cdi` 三個 key

---

### 範例 D — 需要重開機的測試

**User:**
> STC-1750，`client_pcie_lenovo_storagedv`，`os_reboot_stress`。
> 測試內容：OS 重開機 50 次，記錄每次開機時間，最後用 CDI 確認無 SMART 錯誤。
> 工具：OsReboot、CDI。

**AI 行為：**
- 在 `test_main.py` 加入 `@pytest.mark.reboot` marker
- 使用 `OsRebootController`（來自 `lib/testtool/reboot/`）
- 在 `setup_test_class` 加入 `framework.reboot_manager` 必要的 hook 說明
- Config.json 加入 `reboot` key（cycle count、timeout）

---

### 範例 E — 只想加步驟到現有 test case

**User:**
> STC-1685（stc1685_burnin）目前最後一步是 `test_05_cdi_after`，
> 我想在後面加一個 `test_06_validate_log`，用來確認 burnin log 裡沒有 error 字串。

**AI 行為：**
- 讀取現有 `test_main.py` 結尾
- 在 `test_05_cdi_after` 之後插入新方法 `test_06_validate_log`
- 加上 `@pytest.mark.order(6)` 與 `@step(6, "Validate BurnIN log for errors")`
- 不修改其他步驟或 Config.json

---

### 範例 F — 確認已建立的 test case 可以被 pytest 收集

**User:**
> 幫我確認剛剛建的 STC-1720 可以正確被 pytest 收集。

**AI 行為（執行 Workflow Step 3）：**
```powershell
python -m py_compile tests/integration/client_pcie_lenovo_storagedv/stc1720_power_cycle/test_main.py
python -m pytest tests/integration/client_pcie_lenovo_storagedv/stc1720_power_cycle/test_main.py --collect-only
```
並回報輸出結果，確認所有 test methods 都被正確收集。

---

### 對答技巧摘要

| 你想做的事 | 建議的開場白 |
|-----------|------------|
| 從零建立完整 test case | `建立 STC-XXXX 的 integration test case，客戶 <client>，步驟如下：...` |
| 讓 AI 主動問你 | `幫我建一個新的 integration test case` |
| 只加一個步驟 | `在 stcXXXX 的 test_main.py 最後加入步驟 test_0N_<name>，做的事是...` |
| 並行步驟 | 在步驟描述中明確說 `同時跑` 或 `concurrent` |
| 需要重開機 | 在步驟中說明 `重開機 N 次` 或 `needs_reboot: true` |
| 確認語法正確 | `幫我 compile 並 collect-only 確認 STC-XXXX` |

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
