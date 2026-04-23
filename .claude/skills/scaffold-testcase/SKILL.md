````skill
---
name: scaffold-testcase
description: Scaffold a new integration test case under tests/integration/test_case/<stcXXXX_name>/ using STC-2557 as the canonical template. Use when user asks to create a new test case, add an integration test, write a test script for a specific STC, or mentions 建 test case, 新增測試, 寫測試腳本, 建立 STC, or similar. Also provides guidance on test step ordering, fixed steps 01-04, pytest markers, RunCard integration, osconfig.yaml, tools.yaml, Runcard.ini, and Config/ design.
---

# Scaffold Integration Test Case Skill

Generate a new integration test case under `tests/integration/test_case/<stcXXXX_name>/`
following the standard architecture defined by `tests/integration/test_case/stc2557_adk_s3s4s5/`.

> **Canonical template:** `tests/integration/test_case/stc2557_adk_s3s4s5/`
> This is the **reference implementation** for all new test cases. It demonstrates
> the complete fixed-steps pattern (01–04), multi-file Config/, setup_test_class,
> and _standard_teardown. Read it before scaffolding any new test.

---

## Standard Directory Structure

```
tests/integration/test_case/<stcXXXX_name>/
├── Config/
│   ├── Config.json           # Tool paths + execution params
│   ├── osconfig.yaml         # OS configuration (power, tasks, auto-login)
│   ├── tools.yaml            # Tool installation declarations
│   └── <tool>.pvt / *.ini   # Optional: tool-specific config files
├── conftest.py               # testcase_config fixture (local)
├── test_main.py              # Main test class (all steps)
├── README.md                 # Test overview and run instructions
└── __init__.py               # Empty, required for pytest discovery
```

### STC naming convention

| Part | Rule | Example |
|------|------|---------|
| `<stcXXXX_name>` | `stc<id>_<short_description>` (lowercase, underscores) | `stc2557_adk_s3s4s5` |

> **Note:** New test cases go directly under `tests/integration/test_case/` — no client subdirectory.

---

## Workflow

### Step 1 — Gather Test Spec

Ask the user (or parse from description):

| Field | Question |
|-------|---------|
| `stc_id` | STC 編號？（如 `2557`） |
| `short_name` | 測試簡稱（snake_case）？（如 `adk_s3s4s5`） |
| `description` | 這個測試做什麼？（一句話說明） |
| `tools_used` | 用到哪些 lib/testtool 的 Controller？（如 CDI, ADKController） |
| `steps` | 步驟 5 開始的自訂步驟有哪些？（注意：步驟 1–4 固定，見下方） |
| `has_concurrent` | 是否有並行測試步驟？（如兩個 Controller 同時跑） |
| `needs_reboot` | 測試中是否需要重開機（steps 5+）？ |

> **注意**：步驟 01~04 是**固定不變**的，所有 testcase 都要包含，見下方「Fixed Workflow Steps 01–04」。

### Step 2 — Generate Files

Generate each file in this order:

1. `__init__.py` — empty
2. `Config/Config.json` — tool paths + execution parameters
3. `Config/osconfig.yaml` — OS configuration settings (copy from stc2557 and modify)
4. `Config/tools.yaml` — tool installation declarations
5. `conftest.py` — `testcase_config` session fixture
6. `test_main.py` — main test class with all steps
7. `README.md` — overview, structure, run instructions

**For complete file templates**, see `references/testcase_templates.md`
**For complete worked example**, see `tests/integration/test_case/stc2557_adk_s3s4s5/`
**For structure rules**, see `references/testcase_structure.md`

### Step 3 — Verify

```powershell
# 1. Check for syntax errors
python -m py_compile tests/integration/test_case/<stcXXXX_name>/test_main.py

# 2. Run collection test (discovers test methods without executing them)
python -m pytest tests/integration/test_case/<stcXXXX_name>/test_main.py --collect-only

# Full run (requires hardware + installed tools)
python -m pytest tests/integration/test_case/<stcXXXX_name>/test_main.py -v -s
```

**Verification checklist:**
- [ ] `test_main.py` syntax is valid (py_compile succeeds)
- [ ] All test methods (test_01 through test_NN) are collected
- [ ] `Config/Config.json`, `Config/osconfig.yaml`, `Config/tools.yaml` all exist
- [ ] No missing imports or fixtures

---

## Fixed Workflow Steps 01–04

**Every** test case must include these four steps unchanged. They establish a clean,
reproducible environment before any test-specific logic begins.

### test_01 — Precondition

```python
@pytest.mark.order(1)
@step(1, "Precondition")
def test_01_precondition(self):
    """Clean testlog (preserve Runcard.ini) and remove stale reboot state."""
    self._cleanup_testlog_directory()          # clears testlog/, preserves Runcard.ini
    clear_log_files()                          # clears log.txt / log.err
    Path(self.log_path).mkdir(parents=True, exist_ok=True)

    # Remove stale reboot state so a re-run always starts fresh.
    state_file = Path(RebootManager.STATE_FILE)
    if state_file.exists():
        state_file.unlink()
        self.reboot_mgr.state = self.reboot_mgr._load_state()
        logger.info(f"[TEST_01] Removed stale reboot state: {state_file}")
```

### test_02 — Install Tools

```python
@pytest.mark.order(2)
@step(2, "Install tools")
def test_02_install_tools(self):
    """Install tools declared in Config/tools.yaml."""
    _tools_yaml = Path(__file__).parent / "Config" / "tools.yaml"
    ToolInstaller(_tools_yaml).install_all()
    logger.info("[TEST_02] Tools installed")
```

### test_03 — Apply OS Configuration

```python
@pytest.mark.order(3)
@step(3, "Apply OS configuration")
def test_03_apply_osconfig(self):
    """Apply OS configuration from Config/osconfig.yaml."""
    controller = OsConfigController(
        profile=self._osconfig_profile,
        state_manager=OsConfigStateManager(),
    )
    controller.apply_all()
    TestSTC<XXXX><Name>._osconfig_controller = controller
    logger.info("[TEST_03] OsConfig applied successfully")
```

### test_04 — Clean Environment + Reboot

```python
@pytest.mark.order(4)
@step(4, "Clean Environment")
def test_04_clean_environment(self, request):
    """Remove stale tool dirs, then reboot for a clean platform environment."""
    # Kill and clean tool-specific dirs here (tool-specific, adapt as needed)
    # e.g.: SomeController.kill_processes(); ctrl.cleanup_dirs()

    # REQUIRED: pre-mark BEFORE setup_reboot() calls os._exit(0)
    self.reboot_mgr.pre_mark_completed(request.node.name)

    self.reboot_mgr.setup_reboot(
        delay=10,
        reason="test_04_clean_environment: clean platform environment",
        test_file=__file__,
    )
    # os._exit(0) called inside setup_reboot — code below never executes
```

> **Steps 5+ are test-specific.** Start numbering custom steps from 5.
> Reference implementation: `tests/integration/test_case/stc2557_adk_s3s4s5/test_main.py`

---

## Config/ Files Reference

### Config.json

Contains tool executable paths and execution parameters. Loaded automatically by
`testcase_config.tool_config` (lazy JSON parse).

> **`DUT_info.DiskType` is REQUIRED.** Without it, `RunCard.load_dut_info()` returns
> `False` immediately and all DUT fields in `Runcard.ini` will be empty (Disk Number,
> Capacity, Firmware, CPU, RAM, BIOS, OS, etc.).
> - `0` = PRIMARY disk (C:\\ drive — the SSD under test in most cases)
> - `1` = SECONDARY disk (non-C:\\ NVMe/SSD)

```json
{
  "DUT_info": {
    "DiskType": 0
  },

  "<tool1>": {
    "ExePath": "C:\\tools\\<Tool>\\<exe>.exe",
    "LogPath": "./testlog/<ToolLog>",
    "ScreenShotDriveLetter": "C:"
  },
  "adk": {
    "bpfs_num_iters": 4,
    "bpfb_num_iters": 4,
    "standby_num_iters": 4,
    "hibernate_num_iters": 4
  },
  "smart_check": {
    "drive_letter": "C:",
    "no_increase_attributes": ["Unsafe Shutdowns"],
    "must_be_zero_attributes": []
  }
}
```

### osconfig.yaml

Declares which OS-level settings to apply in `test_03_apply_osconfig`.
Copy from `tests/integration/test_case/stc2557_adk_s3s4s5/Config/osconfig.yaml` and
adjust flags for the new testcase.

Key fields (all default to `false`/disabled unless set):

| Field | What it does |
|-------|-------------|
| `disable_system_restore` | Disables C:\\ system restore via `Disable-ComputerRestore` |
| `disable_memory_diagnostic_tasks` | Disables `\Microsoft\Windows\MemoryDiagnostic\RunFullMemoryDiagnostic` |
| `disable_mcafee_tasks` | Disables McAfee scheduled tasks (no-op if not installed) |
| `disable_fast_startup` | Sets `HiberbootEnabled=0` in registry |
| `enable_hibernation` | Runs `powercfg /hibernate on` |
| `power_plan` | Switches power plan (`"balanced"` / `"high performance"`) |
| `enable_auto_admin_logon` | Enables auto admin logon (requires password resolution) |
| `auto_login_password` | Password for auto-login; leave empty and set env `SSD_TESTKIT_AUTO_LOGIN_PASSWORD` |
| `disable_test_signing` | Runs `bcdedit /set testsigning off` |
| `disable_uac` | Sets `EnableLUA=0` in registry |

### tools.yaml

Declares tools to install via `ToolInstaller`. Tools listed under `phase: pre_runcard`
are installed during `setup_test_class` (before RunCard init). Others are installed
by `test_02_install_tools`.

```yaml
tools:
  - id: smicli
    reinstall: false
    phase: pre_runcard    # RunCard needs SmiCli2.exe to collect DUT info

  - id: windows-adk
    reinstall: false

  - id: cdi
    reinstall: false
```

Tool IDs correspond to entries in `tool-manager/tools-registry.yaml`.

### Tool-Specific Config Files in Config/

Tool-specific binary or config files (e.g. `.pvt`, `.ini`) that must ship with
the test case should be placed in `Config/`. Reference them in `Config.json` as
relative paths and resolve against the test case directory in the test step:

```json
// Config.json
"winpvt": {
    "PvtFile": "Config/winpvt_prod.pvt"
}
```

```python
# In test step — resolve relative path against test case dir
pvt_file = self.config['winpvt'].get('PvtFile', '').strip()
if pvt_file:
    pvt_path = Path(pvt_file)
    if not pvt_path.is_absolute():
        pvt_path = Path(__file__).parent / pvt_path
    ctrl_kwargs['pvt_file'] = str(pvt_path)
```

---

## Runcard.ini

`Runcard.ini` is the test result record written by `RunCard.start_test()`. It is
stored under `./testlog/Runcard.ini` (the `TESTLOG_DIR` path).

**How it is generated:**
1. `setup_test_class` calls `cls._init_runcard(runcard_params)` → `RunCard.start_test()`
2. `start_test()` collects DUT info via SmiCli and writes `Runcard.ini` to `./testlog/`
3. At teardown, `cls._teardown_runcard(request.session)` writes PASS/FAIL into the file

**Why it is preserved during cleanup:**
`_cleanup_testlog_directory()` in `test_01_precondition` skips `Runcard.ini` so it
is not destroyed before the test finishes:

```python
# In BaseTestCase._cleanup_testlog_directory:
if item.name == 'Runcard.ini':
    continue  # preserve RunCard.ini written by start_test()
```

`Runcard.ini` contains: `[Info]` (case ID, script version, DUT model/FW/SN)
and `[Result]` (PASS/FAIL, start/end time).

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

### New-style Class Variable Pattern (current standard)

**`setup_test_class` は不要** — BaseTestCase が自動で処理する。
testcase は class variables を宣告するだけ：

```python
class TestSTCXXXX<Name>(BaseTestCase):
    # ── 必填：這 4 行取代整個 setup_test_class ───────────────────────
    _TESTCASE_FILE = __file__                          # BaseTestCase が __file__ を受け取る
    _CONFIG_DIR    = Path(__file__).parent / "Config"
    _LOG_ENV_VAR   = "TOOL_LOG_DIR"   # log base path の env var（空ならデフォルト）
    _LOG_SUBDIR    = "subdir_name"    # testlog 下的子目錄
    # ──────────────────────────────────────────────────────────────────
    _osconfig_controller = None       # test_03 が設定する

    # ADK 等の testcase-specific init があれば override（不要なら省略）：
    @classmethod
    def _on_extra_setup(cls, test_dir: Path) -> None:
        cls.adapter = VersionAdapter(get_build_number())

    # test_01 ~ test_NN のみ
```

**BaseTestCase.setup_test_class が自動でやること：**
```
_setup_working_directory(_TESTCASE_FILE)
→ load Config/Config.json へ cls.config
→ _resolve_log_path(_LOG_ENV_VAR, _LOG_SUBDIR) へ cls.log_path
→ load Config/osconfig.yaml（存在する場合）へ cls._osconfig_profile
→ RebootManager(total_tests, auto_login_config)
→ ToolInstaller(Config/tools.yaml).install_pre_runcard()（存在する場合）
→ _on_extra_setup(test_dir)       ← subclass hook
→ _init_runcard(runcard_params)   or cls.runcard = None（recovering 時）
yield
→ _standard_teardown(session, osconfig_yaml, _osconfig_controller, logger)
```

**設計原則：**
- `osconfig.yaml` がない testcase → profile load をスキップ、auto_login = `{}`
- `tools.yaml` がない testcase → install_pre_runcard をスキップ
- `_LOG_ENV_VAR` / `_LOG_SUBDIR` が空 → `cls.log_path = str(test_dir / "testlog")`
- `_on_extra_setup` は no-op がデフォルト。override 不要なら書かなくていい

**Function-level の auto-skip/mark は引き続き自動：**
```
For each test_XX method (BaseTestCase.setup_teardown_function, automatic):
├── is_completed(test_name) → pytest.skip if True   ← auto-skip
├── [yield — test body]
└── mark_completed(test_name)                       ← auto-mark
```

---

## ⚠️ Critical Rule: `pre_mark_completed` Before Every `setup_reboot()`

**`setup_reboot()` calls `os._exit(0)` — the current pytest process is terminated immediately.**

`BaseTestCase.setup_teardown_function` auto-marks a step as completed in its `yield` teardown,
but that teardown **never executes** when `os._exit(0)` forcibly kills the process.

**Result without `pre_mark_completed`:** the step does NOT appear in `completed_tests` in the
reboot state file → after reboot, RebootManager re-runs the same step → `setup_reboot()` again
→ **infinite reboot loop**.

### Required Pattern

Every test step that calls `setup_reboot()` **MUST** accept `request` as a parameter and call
`pre_mark_completed` **immediately before** `setup_reboot()`:

```python
@pytest.mark.order(4)
@step(4, "Clean Environment")
def test_04_clean_environment(self, request):   # ← add `request` parameter
    """..."""
    # do work...
    ctrl.cleanup_dirs()

    # ✅ REQUIRED: pre-mark BEFORE setup_reboot() calls os._exit(0)
    self.reboot_mgr.pre_mark_completed(request.node.name)

    self.reboot_mgr.setup_reboot(
        delay=10,
        reason="...",
        test_file=__file__,
    )
    # os._exit(0) is called inside setup_reboot — code below never executes
```


### Checklist

- [ ] Any step that calls `setup_reboot()` accepts `request` as a parameter
- [ ] `pre_mark_completed(request.node.name)` is called immediately before `setup_reboot()`
- [ ] The docstring notes: `# os._exit(0) is called inside setup_reboot — code below never executes`

### Real-world examples in this codebase

| Test | Step | Pattern |
|------|------|---------|
| `stc2557_adk_s3s4s5` | `test_04_clean_environment` | `pre_mark_completed` + `setup_reboot` |
| `stc2562_modern_standby` | `test_05_clear_sleep_history` | `pre_mark_completed` + `setup_reboot` |
| `stc2562_modern_standby` | `test_09_clear_sleepstudy_and_reboot` | `pre_mark_completed` + `setup_reboot` |

> **Note:** `prepare_for_external_reboot()` does NOT call `os._exit(0)` — it only persists state
> and writes the BAT. Steps using only `prepare_for_external_reboot()` (followed by an external
> tool triggering the reboot) do NOT need `pre_mark_completed`; the auto-mark in
> `setup_teardown_function` will run normally after `prepare_for_external_reboot()` returns.

#### Fixture Parameters

| Parameter | Defined in | What it provides |
|-----------|-----------|-----------------|
| `testcase_config` | test case's own `conftest.py` | `TestCaseConfiguration` — `case_id`, `bin_directory`, `tool_config` (parsed Config.json) |
| `runcard_params` | `tests/integration/conftest.py` (shared) | Dict with `'initialization'` and `'start_params'` keys for RunCard init |
| `test_params` | test case's own `conftest.py` | `@dataclass` with tunable thresholds/durations — used as a **test method** parameter, not in the fixture |

#### BaseTestCase Helper Methods

| Method | Where to call | What it does |
|--------|--------------|--------------|
| `cls._setup_working_directory(__file__)` | 1st line of setup | Resolves test dir, `os.chdir()`, calls `logConfig()`; returns `Path` |
| `cls._count_test_methods()` | `RebootManager(total_tests=...)` | Counts `test_*` methods; used by `all_tests_completed()` |
| `cls._init_runcard(runcard_params)` | after RebootManager | Non-fatal RunCard start; sets `cls.runcard` (`None` on error) |
| `cls._teardown_runcard(request.session)` | teardown | Calls `runcard.end_test(PASS/FAIL)`; no-op when `cls.runcard is None` |
| `cls._teardown_reboot_manager()` | last teardown step | Calls `reboot_mgr.cleanup()`, swallows all exceptions |

#### Initialisation Order Rules

| Order | Must do before | Reason |
|-------|---------------|--------|
| `_setup_working_directory` | everything else | All relative paths depend on cwd |
| `RebootManager(...)` | after `os.chdir` | STATE_FILE is relative (`"./pytest_reboot_state.json"`) |
| `os.chdir(original_cwd)` | absolute last in teardown | Restores cwd for subsequent code |

### conftest.py Pattern

```python
import pytest
from pathlib import Path
from dataclasses import dataclass
from tests.integration.conftest import TestCaseConfiguration

@pytest.fixture(scope="session")
def testcase_config():
    case_root_dir = Path(__file__).parent
    config = TestCaseConfiguration(case_root_dir)
    # Optional overrides (e.g., custom smicli path):
    # config.smicli_executable = case_root_dir / "bin/SmiWinTools/bin/x64/SmiCli2.exe"
    return config

# Optional: tunable test parameters (used as fixture in individual test methods)
@dataclass
class STCXXXXParams:
    some_duration_min: int = 60
    some_threshold: int = 90

@pytest.fixture(scope="session")
def test_params() -> STCXXXXParams:
    return STCXXXXParams()
```

The shared `runcard_params` fixture is in `tests/integration/conftest.py` and is
**automatically available** — no import needed in your conftest.

---

## Pytest Markers

Apply markers on the test class level. Use `@pytest.mark.<marker>` for:

| Category | Marker examples |
|----------|----------------|
| Client | `@pytest.mark.client_lenovo`, `@pytest.mark.client_samsung`, `@pytest.mark.client_hp` |
| Interface | `@pytest.mark.interface_pcie`, `@pytest.mark.interface_sata` |
| Project | `@pytest.mark.project_storagedv`, `@pytest.mark.project_burnin`, `@pytest.mark.project_standard` |
| Feature | `@pytest.mark.feature_burnin`, `@pytest.mark.feature_smart`, `@pytest.mark.feature_power` |
| Tool requirement | `@pytest.mark.requires_winpvt`, `@pytest.mark.requires_cdi` |
| Speed | `@pytest.mark.slow` (for tests > 30 min) |

Register new markers in `pytest.ini` under `markers =`. The project uses `--strict-markers`.

---

## Testlog Cleanup Pattern

`test_01_precondition` must clean **all** log/output files so each full run starts fresh.

### When to use which approach

| Scenario | Recommended approach |
|----------|---------------------|
| Standard case — full testlog wipe is OK | Call `self._cleanup_testlog_directory()` (BaseTestCase built-in) — no custom method needed |
| Special case — need to preserve specific subdirs/files | Implement local `_cleanup_test_logs()` and call it **instead of** `_cleanup_testlog_directory()` |

`_cleanup_testlog_directory()` (from `framework/base_test.py`) wipes the entire `./testlog/`
directory (all files and subdirs), except `Runcard.ini`, then recreates it empty. This is the
**preferred default** for most test cases.

### Mandatory cleanup items

| 類型 | 清除對象 | 範例 |
|------|---------|------|
| **工具 log 目錄** | 每個 Controller 的 log output dir | `cleanup_directory('./testlog/CDILog', ...)` |
| **單一輸出檔** | HTML 報告、結果 JSON 等 | `sleepstudy-report.html` |
| **測試 log 檔** | `log.txt`、`log.err` (由 logger 產生) | 每次執行都會累加，必須明確刪除 |
| **Reboot state** | `./testlog/reboot_state.json` | 僅需要重開機的測試案例 |

### 必須明確刪除 `log.txt` / `log.err`

這兩個檔案由 `logConfig()` 在 `setup_test_class` 中建立，**不會被 `cleanup_directory` 自動刪除**（因 cleanup 在 test_01 執行，此時 logger 已啟動並持有 file handle）。

```python
# Standard case — call BaseTestCase built-in (preferred default)
def test_01_precondition(self):
    self._cleanup_testlog_directory()   # wipes testlog/, preserves Runcard.ini
    clear_log_files()
    Path(self.log_path).mkdir(parents=True, exist_ok=True)
    ...
```

```python
# Special case — custom method when specific subdirs must be preserved
def _cleanup_test_logs(self) -> None:
    log_path = self.config.get('log_path', './log/STC-XXXX')

    # 1. Reboot state (if applicable)
    # state_file = Path('./testlog/reboot_state.json')
    # if state_file.exists(): state_file.unlink()

    # 2. Tool log dirs
    cleanup_directory('./testlog/CDILog', 'CDI log directory', logger)
    # cleanup_directory('./testlog/PwrTestLog', 'PwrTest log directory', logger)
    # ...add one line per tool used...

    # 3. Single file outputs
    # ss_report = Path('./testlog/sleepstudy-report.html')
    # if ss_report.exists(): ss_report.unlink()

    # 4. Main test log directory + log.txt / log.err
    cleanup_directory(log_path, 'test log directory', logger)
    log_dir = Path(log_path)
    for log_file in ['log.txt', 'log.err']:
        p = log_dir / log_file
        if p.exists():
            try:
                p.unlink()
            except Exception as exc:
                logger.warning(f"Could not remove {p}: {exc}")
```

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

### Stale Process Cleanup Before GUI Tool Launch

Before launching a GUI tool, kill any lingering process from a previous interrupted run.
Do **not** raise an error when the process is not found — `returncode != 0` is expected
on a clean machine:

```python
import subprocess
result = subprocess.run(
    ['taskkill', '/F', '/IM', 'WinPVT.exe'],
    capture_output=True,
)
if result.returncode == 0:
    logger.info("[TEST_0N] Killed stale WinPVT.exe process(es) before startup")
# No error raised if process not found (returncode != 0 is normal)
```

Replace `WinPVT.exe` with the actual process image name of the tool being launched.

### close_app() — Explicit Close for GUI Tools

GUI tools that do not self-terminate after completion must be closed explicitly:

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

# 6. Close GUI (for tools that don't self-terminate)
ctrl.close_app()
```

Call `close_app()` even on failure paths when the process may still be running, to avoid
leaving ghost processes that would interfere with the next run.

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

## SmartCheck Before/After SMART Comparison Pattern

Use when the test must verify SSD SMART health before and after a stress run via
`SmartCheckController` + `SmartCheckLogParser`:

**Imports:**
```python
from lib.testtool.smartcheck import SmartCheckController, SmartCheckLogParser
```

**Module-level constant (outside class):**
```python
MONITORED_ATTRIBUTES = [
    "Critical Warning",
    "Power Cycles",
    "Unsafe Shutdowns",
    "Media and Data Integrity Errors",
    "Number of Error Information Log Entries",
]
_smartcheck_parser = SmartCheckLogParser(MONITORED_ATTRIBUTES)
```

**Pre-check step (test_0N):**
```python
def test_0N_smartcheck_pre(self):
    smart_cfg = self.config.get('smartcheck', {})
    ctrl = SmartCheckController(
        output_dir=smart_cfg.get('output_dir_before', './testlog/SmartCheckLog_before'),
    )
    ctrl.set_config(
        total_time=smart_cfg.get('total_time', 3),
        check_interval=smart_cfg.get('check_interval', 3),
        timeout=smart_cfg.get('timeout', 10),
    )
    ctrl.start()
    ctrl.join(timeout=ctrl.timeout * 60 + 30)

    if ctrl.is_alive():
        ctrl.stop()
        ctrl.join(timeout=10)
        pytest.fail("[TEST_0N] SmartCheck pre-check timed out")
    if ctrl.status is False:
        pytest.fail("[TEST_0N] SmartCheck detected SMART errors — aborting")
```

**Post-check step (test_0M):** identical structure, use `output_dir_after`.

**Compare step (test_0M+1):**
```python
def test_0P_compare_smartcheck(self):
    before_log = Path('./testlog/SmartCheckLog_before/SmartCheck.log')
    after_log  = Path('./testlog/SmartCheckLog_after/SmartCheck.log')
    try:
        ok, failures = _smartcheck_parser.compare_no_increase(
            before_log=before_log,
            after_log=after_log,
        )
    except (FileNotFoundError, ValueError) as exc:
        pytest.fail(f"{exc}")
    if not ok:
        pytest.fail(
            "SmartCheck SMART attributes must not increase. Violations:\n"
            + "\n".join(f"  {m}" for m in failures)
        )
```

**Config.json entries:**
```json
"smartcheck": {
    "output_dir_before": "./testlog/SmartCheckLog_before",
    "output_dir_after":  "./testlog/SmartCheckLog_after",
    "total_time": 3,
    "check_interval": 3,
    "timeout": 10
}
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

### Mid-Test Cycle Count Update

When a test step completes a countable iteration (e.g., stress cycles), update RunCard
before closing the controller:

```python
cycles = ctrl.cycles          # retrieve completed cycle count from controller
if self.runcard is not None and cycles > 0:
    self.runcard.update_test_status(test_cycle=cycles)
    self.runcard.save_to_file()
    logger.info(f"[TEST_0N] Runcard updated: Test Cycle={cycles}")

# Close GUI after saving Runcard, so the record is saved even if close fails
ctrl.close_app()
```

- Always guard with `if self.runcard is not None`.
- Call `update_test_status` / `save_to_file` **before** `ctrl.close_app()`.

---

## Known Test Cases Reference

| STC | Directory | Description |
|-----|-----------|-------------|
| **STC-2557** ⭐ | `tests/integration/test_case/stc2557_adk_s3s4s5/` | **Canonical template** — ADK S3/S4/S5 power state tests with fixed steps 01–04, OsConfig, ToolInstaller, RebootManager |
| **STC-1067** | `tests/integration/test_case/stc1067_winpvt_standby_critical/` | SmartCheck before/after SMART pattern · GUI tool automation (WinPVT) · `.pvt` config in Config/ · RunCard mid-test cycle update |
| **STC-1685** | `tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/` | Legacy template — BurnIN install + 24h disk stress + SMART monitor (older pattern, no osconfig.yaml/tools.yaml) |

---

## Example AI Conversations

以下範例示範如何與 AI 對答，讓它套用此 skill 建立 integration test case。

---

### 範例 A — 最簡短的開場白（讓 AI 主動提問）

**User:**
> 幫我在 tests/integration/test_case 底下建立一個新的 STC 測試案例。

**AI 回應（依 Workflow Step 1 逐一確認）：**
> 好的！請提供以下資訊：
> 1. STC 編號？（如 `2600`）
> 2. 測試簡稱？（snake_case，如 `smart_monitor`）
> 3. 這個測試做什麼？（一句話說明）
> 4. 用到哪些 testtool Controller？（CDI / ADKController / ...）
> 5. 步驟 5 開始的自訂步驟有哪些？（步驟 1–4 固定，無需列出）
> 6. 是否有並行步驟？步驟 5+ 是否需要重開機？

---

### 範例 B — 一次提供所有資訊

**User:**
> 幫我建立 STC-2600 的 integration test case。
> - 簡稱：`power_cycle`
> - 說明：對 SSD 執行 100 次電源循環，並在前後用 CDI 擷取 SMART 數據比對。
> - 用到的工具：CDI
> - 自訂步驟（step 5+）：
>   5. CDI before（取 SMART baseline）
>   6. 電源循環 100 次（透過外部工具）
>   7. CDI after（取 SMART 數據）
>   8. SMART 比對（Unsafe Shutdowns 不能增加，錯誤計數必須為 0）
> - 無並行，無需重開機

**AI 行為：** 直接進入 Step 2，依序產生以下檔案：

```
tests/integration/test_case/stc2600_power_cycle/
├── __init__.py
├── Config/
│   ├── Config.json
│   ├── osconfig.yaml
│   └── tools.yaml
├── conftest.py
├── test_main.py
└── README.md
```

test_main.py 包含 test_01~test_04（固定），加上 test_05~test_08（自訂）。

**AI 行為（Step 3 — 驗證）：**
```powershell
python -m pytest tests/integration/test_case/stc2600_power_cycle/ --collect-only -q
```

---

### 範例 C — 並行測試（兩個 Controller 同時跑）

**User:**
> 建立 STC-2610，名稱 `burnin_smart_concurrent`。
> 自訂步驟（5+）：
> 5. CDI before
> 6. BurnIN + SmartCheck 同時跑 8 小時
> 7. CDI after + SMART 比對
> 沒有重開機需求（步驟 5+ 無需 reboot）。

**AI 行為：**
- 固定步驟 01–04 照常產生
- 在 `test_06_burnin_with_smart` 套用 **Concurrent Test Pattern**
- Config.json 包含 `burnin`、`smartcheck`、`cdi` 三個 key

---

### 範例 D — 只想加步驟到現有 test case

**User:**
> STC-2557（stc2557_adk_s3s4s5）目前最後一步是 `test_14_smart_compare`，
> 我想在後面加一個 `test_15_validate_log`，用來確認 AxeLog.txt 裡沒有 error 字串。

**AI 行為：**
- 讀取現有 `test_main.py` 結尾
- 在 `test_14_smart_compare` 之後插入新方法 `test_15_validate_log`
- 加上 `@pytest.mark.order(15)` 與 `@step(15, "Validate AxeLog for errors")`
- 不修改其他步驟或 Config 檔

---

### 範例 E — 確認已建立的 test case 可以被 pytest 收集

**User:**
> 幫我確認剛剛建的 STC-2600 可以正確被 pytest 收集。

**AI 行為（執行 Workflow Step 3）：**
```powershell
python -m py_compile tests/integration/test_case/stc2600_power_cycle/test_main.py
python -m pytest tests/integration/test_case/stc2600_power_cycle/test_main.py --collect-only
```
並回報輸出結果，確認所有 test methods 都被正確收集。

---

### 對答技巧摘要

| 你想做的事 | 建議的開場白 |
|-----------|------------|
| 從零建立完整 test case | `建立 STC-XXXX 的 integration test case，步驟如下：...` |
| 讓 AI 主動問你 | `幫我建一個新的 integration test case` |
| 只加一個步驟 | `在 stcXXXX 的 test_main.py 最後加入步驟 test_0N_<name>，做的事是...` |
| 並行步驟 | 在步驟描述中明確說 `同時跑` 或 `concurrent` |
| 步驟 5+ 需要重開機 | 在步驟中說明 `重開機` 或 `needs_reboot: true` |
| 確認語法正確 | `幫我 compile 並 collect-only 確認 STC-XXXX` |

---

## Related Files

- **Canonical template** ⭐: `tests/integration/test_case/stc2557_adk_s3s4s5/` — read `test_main.py`, `conftest.py`, and all `Config/` files before scaffolding
- **Shared conftest/fixtures**: `tests/integration/conftest.py` — `TestCaseConfiguration`, `runcard_params`
- **Base test class**: `framework/base_test.py` — `BaseTestCase`, `_standard_teardown`, `_build_auto_login_cfg`, `_resolve_log_path`
- **Step decorator**: `framework/decorators.py` — `@step(N, "description")`
- **Logger**: `lib/logger.py` — `get_module_logger(__name__)`, `logConfig()`, `write_session_footer()`, `clear_log_files()`
- **Tool installer**: `lib/testtool/tool_installer.py` — `ToolInstaller(tools_yaml).install_all()` / `.install_pre_runcard()`
- **OsConfig**: `lib/testtool/osconfig/` — `OsConfigController`, `OsConfigStateManager`, `load_profile`
- **Tools registry**: `tool-manager/tools-registry.yaml` — tool IDs used in `tools.yaml`
- **File templates**: `.claude/skills/scaffold-testcase/references/testcase_templates.md`
- **Structure rules**: `.claude/skills/scaffold-testcase/references/testcase_structure.md`

````
