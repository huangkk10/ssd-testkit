---
name: scaffold-testtool
description: Scaffold a new testtool library sub-package under lib/testtool/ using the burnin package as the standard template. Use when user asks to create a new testtool, add a library for a tool, migrate a legacy single-file testtool, scaffold a testtool package, or mentions 建 testtool, 新增工具 library, 遷移, or wrapping a CLI/GUI/BAT tool. Also answers questions about known tools (PHM, burnin, CDI, smartcheck, PwrTest, OsReboot, OsConfig) — check the Known Tools Reference section and read the corresponding reference file.
---

# Scaffold Testtool Library Skill

Generate a new `lib/testtool/<toolname>/` sub-package following the standard architecture defined by `lib/testtool/burnin/`.

## Standard Package Structure

Every testtool library follows this layout:

```

## PHM Web UI — Quick Automation Guide

- **Automation method**: Use Playwright (Python sync API). PHM runs a Node.js web UI at `http://localhost:1337`.
- **Primary selectors**:
    - Preset radios: use attribute id selector — `[id="chk_coll_sc_{Scenario Name}"]` (IDs may contain spaces).
    - Preset labels: `[id="lbl_coll_sc_{Scenario Name}"]`.
    - Per-scenario counter host: `id="app-collector-{scenario_short}-cnt_coll_op_{Option Name}"` with child `input.counter-field` for the numeric input.
    - Show Log textarea: `[id="textArea_daq_logSummary"]` (read with `.input_value()`).
    - Status/banner with traces info: `[id="lbl_coll_statusMsg"]` contains `Traces saved to <path>`.
- **Common workflow**:
    1. Navigate to Collector tab (`http://localhost:1337` → open Collector view).
    2. Select preset scenario by clicking the radio: click the radio locator then verify `.is_checked()`.
    3. Expand "Collection Options" accordion if collapsed.
    4. Set numeric counters (Delayed Start / Scenario Duration / Cycle Count) by targeting the host id, focusing the `input.counter-field`, using `click(click_count=3)` to select existing value, `page.fill()` or `page.type()`, and dispatching `input`/`change` events if needed.
    5. Click Start and then poll the Show Log for the sentinel `Data analysis finished.` to detect run completion.
    6. After completion, read `[id="lbl_coll_statusMsg"]` and extract the substring after `Traces saved to ` to obtain the traces folder path.
- **Robustness & debugging tips**:
    - Use exact attribute id selectors (`[id="..."]`) because IDs contain spaces and special chars.
    - Always verify state after action (e.g., `.is_checked()` for radios, `.input_value()` for inputs).
    - If selectors fail, save the page HTML (`page.content()` → tmp file) and run a local ID-extraction script to confirm actual ids.
    - Prefer waiting for visibility/stability before interacting (`locator.wait_for(state="visible")`).
    - For numeric counters, triple-click semantics are `click(click_count=3)` in Playwright; `triple_click()` is not available.
    - When test runs finish, the PHM status label contains the traces path; copy the traces directory into your verification folder for archiving using `shutil.copytree()`.
- **Reference implementation**: See `lib/testtool/phm/ui_monitor.py` for helper methods: `select_preset_scenario()`, `expand_collection_options()`, `_fill_counter_field()`, `get_log_text()`, `wait_for_completion()`, and `get_traces_path()`.
lib/testtool/<toolname>/
├── __init__.py          # Package entry, exports, docstring with usage example
├── config.py            # DEFAULT_CONFIG, type validation, merge_config()
├── controller.py        # Main controller (inherits threading.Thread)
├── exceptions.py        # Exception hierarchy (Base → sub-classes)
├── process_manager.py   # Install/Start/Stop/Kill lifecycle  [optional]
├── script_generator.py  # Script/config file generation      [optional]
├── ui_monitor.py        # pywinauto UI automation            [optional]
└── log_parser.py        # Structured log/report file parser  [optional]
```

Optional modules are only created when the tool spec requires them:
- `process_manager.py` → when `requires_install: true`
- `script_generator.py` → when `has_script_generator: true`
- `ui_monitor.py` → when `has_ui: true`
- `log_parser.py` → when `has_log_parser: true`
- `state_manager.py` → when `has_state_manager: true` (cross-reboot / cross-process JSON state persistence)

## Workflow

### Step 1 — Gather Tool Spec

Ask the user (or parse from their description) the following:

| Field | Question to ask |
|-------|----------------|
| `tool_name` | 工具的 PascalCase 名稱？（如 `DiskInfo`） |
| `package_name` | 目錄名稱（snake_case）？（如 `diskinfo`） |
| `description` | 這個工具做什麼？ |
| `execution.type` | 執行方式：`cli` / `gui` / `bat` / `api`？ |
| `execution.executable` | 執行檔名稱？（如 `DiskInfo64.exe`） |
| `requires_install` | 需要安裝流程嗎？（`true`/`false`） |
| `has_ui` | 有 GUI 視窗需要 pywinauto 監控嗎？ |
| `has_script_generator` | 需要產生 .bits/.ini 等腳本嗎？ |
| `config_params` | 有哪些設定參數？（名稱、型別、預設值） |
| `result_parsing.method` | 怎麼判斷 Pass/Fail？`log_file` / `stdout` / `runcard` / `ui` |
| `result_parsing.pass_pattern` | Pass 的特徵字串或 regex |
| `result_parsing.fail_pattern` | Fail 的特徵字串或 regex |

**For full schema details**, see `references/tool_spec_schema.md`

### Step 2 — Generate Files

Generate each file in this order:

1. `exceptions.py` — exception hierarchy
2. `config.py` — configuration class
3. `state_manager.py` — (if `has_state_manager: true`) — before controller, controller depends on it
4. `controller.py` — main threading controller
5. `process_manager.py` — (if `requires_install: true`)
6. `script_generator.py` — (if `has_script_generator: true`)
7. `ui_monitor.py` — (if `has_ui: true`)
8. `log_parser.py` — (if `has_log_parser: true`)
9. `__init__.py` — exports + usage docstring

**For module-by-module templates**, see `references/module_templates.md`  
**For a complete worked example**, see `references/burnin_example.md`

### Step 3 — Generate Test Skeleton

Create `tests/unit/lib/testtool/test_<package_name>/` with:

```
tests/unit/lib/testtool/test_<package_name>/
├── __init__.py           # empty, required for pytest discovery
├── conftest.py           # shared fixtures (temp_dir, sample_config)
├── test_exceptions.py    # pytest style — raise + inheritance for every exception class
├── test_config.py        # pytest style — get_default_config / validate / merge
└── test_controller.py    # pytest style — @pytest.fixture, @pytest.mark.parametrize, mocked deps
```

Optional (create only if the corresponding module exists):
- `test_state_manager.py` — if `has_state_manager: true`
- `test_process_manager.py` — if `requires_install: true`
- `test_script_generator.py` — if `has_script_generator: true`
- `test_ui_monitor.py` — if `has_ui: true`
- `test_log_parser.py` — if `has_log_parser: true`

**Key rules:**
- All test files (`test_exceptions.py`, `test_config.py`, `test_controller.py`) → use **pytest** style
- `test_controller.py`: use `@pytest.fixture(autouse=True)` for path patches, `@pytest.fixture` for the controller instance, `@pytest.mark.parametrize` for multi-exception cases
- **Never** call real executables or touch the real file system — mock everything
- Patch `pathlib.Path.exists`, `subprocess.Popen`, sub-components as needed
- `status` property: assert `None` before `start()`, `True`/`False` after `join()`
- Shared fixtures go in `conftest.py`; adapt `sample_config` to tool's required params

**For complete templates and examples**, see `references/test_templates.md`

### Step 4 — Generate Integration Test Skeleton

Create `tests/integration/lib/testtool/test_<package_name>/` with:

```
tests/integration/lib/testtool/test_<package_name>/
├── __init__.py
├── conftest.py                          # env fixture + env-var overrides + skip guard
└── test_<package_name>_workflow.py      # real-executable tests (no mocks)
```

Also add a `"<package_name>"` section to `tests/integration/Config/Config.json`:
```json
"<package_name>": {
    "ExePath": "./bin/<ToolDir>/<executable>",
    "LogPath": "./testlog/<Tool>Log",
    "timeout": 120
}
```

> **Config.json design principle:** Only environment/path params (exe path, log dir, OS-version) belong here.
> Execution params (`cycle_count`, `delay_seconds`, `wake_after_seconds`, etc.) vary per test — pass them as explicit kwargs to the controller inside each test function, **not** through Config.json or the env fixture.

**Key rules:**
- Tool executable path: support `<TOOL>_EXE_PATH` environment variable override; default to `tests/unit/lib/testtool/bin/<ToolDir>/`
- Use `pytest.skip()` in `check_environment` if executable not found — never fail due to missing binary
- Tag every test with `@pytest.mark.integration` and `@pytest.mark.requires_<package_name>`
- **No mocks** — integration tests must run the real executable
- Each test gets an isolated `clean_log_dir` (timestamped sub-directory)
- **`__init__.py` at every level**: `tests/integration/lib/`, `tests/integration/lib/testtool/`, and `tests/integration/lib/testtool/test_<package_name>/` all require an empty `__init__.py` — otherwise VS Code Test Explorer cannot discover the tests
- **Register marker in `pytest.ini`**: append `requires_<package_name>: ...` to the `markers` list; the project uses `--strict-markers` so undeclared markers cause collection errors
- **`check_environment` MUST be a `@pytest.fixture(scope="session")`** — NEVER call `pytest.skip()` at module level in conftest.py; doing so skips the entire conftest at collection time and makes all tests invisible to VS Code Test Explorer. See `references/integration_test_templates.md` for the correct pattern.
- **Selective guard application**: Only attach `check_environment` as a fixture parameter to tests that actually cause dangerous side effects (e.g., real reboot, real install). Tests that are safe regardless (e.g., recovery-detection via pre-populated state file) should NOT request `check_environment` so they always run.

**For complete templates**, see `references/integration_test_templates.md`

### Step 5 — Verify

After generating:
```powershell
# Check for syntax errors
python -m py_compile lib/testtool/<package_name>/*.py

# Run unit tests
python -m pytest tests/unit/lib/testtool/test_<package_name>/ -v

# Run integration tests (requires real executable)
python -m pytest tests/integration/lib/testtool/test_<package_name>/ -v -m "integration"

# Skip integration tests during normal dev
python -m pytest tests/ -m "not integration"
```

---

## Module Generation Rules

### `exceptions.py`

Always generate these base exceptions. Add tool-specific ones based on the spec:

```python
class <Tool>Error(Exception): ...             # always
class <Tool>ConfigError(<Tool>Error): ...     # always
class <Tool>TimeoutError(<Tool>Error): ...    # always
class <Tool>ProcessError(<Tool>Error): ...    # always
class <Tool>InstallError(<Tool>Error): ...    # only if requires_install: true
class <Tool>UIError(<Tool>Error): ...         # only if has_ui: true
class <Tool>LogParseError(<Tool>Error): ...   # only if has_log_parser: true
class <Tool>StateError(<Tool>Error): ...      # only if has_state_manager: true
class <Tool>TestFailedError(<Tool>Error): ... # always
```

### `config.py`

Always include:
- `DEFAULT_CONFIG: Dict[str, Any]` with all params and their defaults
- `VALID_PARAMS: set = set(DEFAULT_CONFIG.keys())`
- `PARAM_TYPES: Dict[str, type]` for validation
- `@classmethod get_default_config(cls) -> Dict[str, Any]`
- `@classmethod validate_config(cls, config: Dict) -> bool`
- `@classmethod merge_config(cls, base: Dict, overrides: Dict) -> Dict`

### `controller.py`

Always inherit from `threading.Thread`. Minimum interface:

```python
class <Tool>Controller(threading.Thread):
    def __init__(self, **kwargs): ...
    def set_config(self, **kwargs) -> None: ...
    def run(self) -> None: ...          # thread body
    def stop(self) -> None: ...         # signal stop
    @property
    def status(self) -> Optional[bool]: ...  # None=running, True=pass, False=fail
    @property
    def error_count(self) -> int: ...
```

If `requires_install: true`, also add:
```python
    def is_installed(self) -> bool: ...
    def install(self) -> None: ...
    def uninstall(self) -> None: ...
```

### `__init__.py`

Structure:
```python
"""
<Tool> Package
...usage example showing minimum runnable code...
"""
from .controller import <Tool>Controller
from .config import <Tool>Config
from .exceptions import <Tool>Error, <Tool>ConfigError, ...

__version__ = '1.0.0'
__all__ = [...]
```

---

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Package directory | `snake_case` | `disk_info` |
| Class prefix | `PascalCase` tool name | `DiskInfo` |
| Controller class | `<Tool>Controller` | `DiskInfoController` |
| Config class | `<Tool>Config` | `DiskInfoConfig` |
| Exception base | `<Tool>Error` | `DiskInfoError` |
| Logger | `get_module_logger(__name__)` | (same pattern) |

---

## Common Scenarios

### Scenario 1: Migrate a Legacy Single-file Testtool

Given: `lib/testtool/SomeOldTool.py` (monolithic class)

1. Read the old file to extract: config keys, process commands, result check logic
2. Map old attributes → `DEFAULT_CONFIG` params
3. Map old methods → appropriate module (process vs UI vs controller)
4. Generate the full sub-package
5. Keep the old file as a deprecated alias with an import warning

### Scenario 2: Wrap a New CLI Tool

Given: a CLI tool that takes arguments and exits with a log file

Typical spec:
- `execution.type: cli`
- `requires_install: false`
- `has_ui: false`
- `result_parsing.method: log_file`

Generate: `exceptions.py`, `config.py`, `controller.py`, `__init__.py` only.

### Scenario 3: Wrap a GUI Tool (pywinauto)

Given: a Windows GUI application that must be monitored while running

Typical spec:
- `execution.type: gui`
- `has_ui: true`
- `result_parsing.method: ui`

Generate all 7 modules including `ui_monitor.py`.

---

## Known Tools Reference

For tools that have already been researched and scaffolded, detailed tool-specific specs
(installation paths, ports, unique modules, config params, action items) are documented here.
When a user asks about a known tool, read the corresponding reference file first.

| Tool | Reference | Special Notes |
|------|-----------|---------------|
| **PHM** (Powerhouse Mountain) | `.claude/skills/scaffold-testtool/references/phm.md` | Web App (Node.js + browser); Playwright instead of pywinauto; non-standard `log_parser.py` (PHM test result HTML); `sleep_report_parser.py` is now a backward-compat shim → moved to `SleepStudy`; installed at `C:\Program Files\PowerhouseMountain\PowerhouseMountain.exe`; Web UI `http://localhost:1337` |
| **SleepStudy** | `.claude/skills/scaffold-testtool/references/sleepstudy.md` | Independent `powercfg /sleepstudy` wrapper; migrated from `lib.testtool.phm`; `SleepStudyController(threading.Thread)` + `SleepReportParser` + `SleepStudyConfig`; regex primary / Playwright fallback for HTML parsing; `lib.testtool.phm.sleep_report_parser` is now a re-export shim for backward-compat |
| **PwrTest** | `.claude/skills/scaffold-testtool/references/pwrtest.md` | WDK CLI tool; already bundled in SmiWinTools (no install needed); exe path resolved from `os_name`+`os_version`; non-standard `log_parser.py` for `pwrtestlog.log`/`.xml`; no `process_manager.py` or `ui_monitor.py` |
| **OsReboot** | `.claude/skills/scaffold-testtool/references/reboot.md` | Wraps `shutdown.exe /r /t`; non-standard `state_manager.py` for cross-reboot cycle tracking; no install/UI/log parser; integration tests require isolated machine (`ENABLE_REBOOT_INTEGRATION_TEST=1`) |
| **CDI** (CrystalDiskInfo) | `.claude/skills/scaffold-testtool/references/cdi.md` | GUI tool (pywinauto win32 backend); `CDILogParser` lives in `controller.py` (not a separate `log_parser.py`); `compare_smart_value_no_increase()` for before/after SMART comparison; legacy `CDI.py` deprecated |
| **OsConfig** | `.claude/skills/scaffold-testtool/references/osconfig.md` | Pure Python API (no exe); 34 OS settings via winreg + PowerShell; non-standard `os_compat.py` + `registry_helper.py` + `state_manager.py` + `actions/` sub-directory; fail-soft + idempotent + snapshot/revert; all 6 phases complete |

---

## Related Files

- **Template Reference**: `lib/testtool/burnin/` — canonical library package (full: install + UI + script)
- **Secondary Template**: `lib/testtool/cdi/` — simpler example (UI only, no install, no script)
- **State Manager Template**: `lib/testtool/reboot/state_manager.py` — canonical state_manager with JSON + fsync
- **Log Parser Template**: `lib/testtool/phm/log_parser.py` — canonical log_parser (PHM test result HTML)
- **Sleep Report Parser**: `lib/testtool/sleepstudy/sleep_report_parser.py` — canonical `powercfg /sleepstudy` HTML parser; `SleepReportParser` + `SleepSession`; `start_dt`/`end_dt` accept `str` or `datetime`; regex primary / Playwright fallback; see `references/sleepstudy.md` §6 for full API. (`lib/testtool/phm/sleep_report_parser.py` is now a backward-compat re-export shim.)
- **Sleep Report Parser Tests**: `tests/unit/lib/testtool/test_sleepstudy/test_sleep_report_parser.py` (unit, no browser) + `tests/integration/lib/testtool/test_sleepstudy/test_sleep_report_parser_integration.py` (real Chromium, needs `playwright install chromium`)
- **SleepStudy Tool Reference**: `.claude/skills/scaffold-testtool/references/sleepstudy.md`
- **Unit Test Reference**: `tests/unit/lib/testtool/test_burnin/` — canonical unit test suite
- **Log Parser Test Reference**: `tests/unit/lib/testtool/test_phm/test_log_parser.py` — canonical log_parser test
- **Integration Test Reference**: `tests/integration/lib/testtool/test_cdi/` — canonical integration test
- **Shared Integration Config**: `tests/integration/Config/Config.json` — per-tool path config
- **Shared Integration conftest**: `tests/integration/conftest.py` — `TestCaseConfiguration` class
- **Logger**: `lib/logger.py` — use `get_module_logger(__name__)` in all modules
- **Full Schema**: `.claude/skills/scaffold-testtool/references/tool_spec_schema.md`
- **Burnin Example**: `.claude/skills/scaffold-testtool/references/burnin_example.md`
- **Module Templates**: `.claude/skills/scaffold-testtool/references/module_templates.md`
- **Test Templates**: `.claude/skills/scaffold-testtool/references/test_templates.md`
- **PHM Tool Reference**: `.claude/skills/scaffold-testtool/references/phm.md`

---

## setup_test_class Fixture Pattern

Every integration test class that inherits from `BaseTestCase` defines **one** class-scoped fixture called `setup_test_class`.  It is the single entry point that initialises everything the test needs — working directory, config, `RebootManager`, RunCard — and tears it all down after the session.

> **Reference implementation**: `tests/integration/client_pcie_lenovo_storagedv/stc2562_modern_standby/test_main.py` — `setup_test_class`  
> **Base class helpers**: `framework/base_test.py` — `BaseTestCase`  
> **Shared fixtures source**: `tests/integration/conftest.py` — `TestCaseConfiguration`, `runcard_params`  
> **Per-test-case fixtures**: each test case's own `conftest.py` — `testcase_config`, `test_params`

---

### Why `setup_test_class` lives in the test class (not in `BaseTestCase`)

`BaseTestCase` already defines two autouse fixtures:

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `setup_teardown_class` | `class` | Default minimal setup: creates a generic `RebootManager()`, sets `cls.log_path`, calls `setup_test_environment()` |
| `setup_teardown_function` | `function` | Per-test auto-skip (`is_completed`) + `mark_completed` after each test |

The test class overrides the class-scoped behaviour by defining its own `setup_test_class` fixture.  The function-scoped `setup_teardown_function` from `BaseTestCase` continues to run automatically for every test method — it provides the **auto-skip** and **auto-mark-completed** mechanism without any extra work.

```
pytest session
└── setup_test_class (class scope, defined in TestXxx)   ← YOUR fixture
    ├── _setup_working_directory(__file__)               ← os.chdir + logConfig()
    ├── RebootManager(total_tests=N)                     ← must happen AFTER chdir
    ├── _init_runcard(runcard_params)
    ├── [yield — tests run here]
    ├── _teardown_runcard(request.session)
    ├── _teardown_reboot_manager()                       ← cleanup() state file + BAT
    └── os.chdir(original_cwd)

    For each test_XX method:
    └── setup_teardown_function (function scope, BaseTestCase)
        ├── is_completed(test_name) → pytest.skip if True
        ├── [yield — test body runs]
        └── mark_completed(test_name)
```

---

### Fixture Parameters

`setup_test_class` receives three fixtures from conftest.py:

| Parameter | Defined in | What it provides |
|-----------|-----------|-----------------|
| `testcase_config` | test case's own `conftest.py` | `TestCaseConfiguration` — `case_id`, `bin_directory`, `config_file`, `tool_config` (parsed `Config.json`) |
| `runcard_params` | `tests/integration/conftest.py` (shared) | Dict with `'initialization'` and `'start_params'` keys for `RunCard` init |
| `test_params` | test case's own `conftest.py` | `@dataclass` with test-specific tunable thresholds/durations (e.g., `wake_after_min`, `drips_threshold`) |

`test_params` is used directly in individual test methods (as a function-scope fixture parameter), **not** in the fixture itself.

---

### Canonical Template

```python
@pytest.fixture(scope="class", autouse=True)
def setup_test_class(self, request, testcase_config, runcard_params):
    """Load configuration and initialize test class (runs before all tests)."""
    cls = request.cls
    cls.original_cwd = os.getcwd()

    # ── 1. Working directory + logging ────────────────────────────────
    # Must be the FIRST step — all relative paths (Config.json, state file,
    # testlog/) are anchored to this directory.
    test_dir = cls._setup_working_directory(__file__)
    #   • Resolves test_dir (packaged: path_manager.app_dir; dev: Path(__file__).parent)
    #   • Calls os.chdir(test_dir)
    #   • Calls logConfig() to re-initialise the logger

    # ── 2. Config ──────────────────────────────────────────────────────
    cls.config = testcase_config.tool_config   # parsed Config/Config.json
    cls.bin_path = testcase_config.bin_directory

    # ── 3. RebootManager ─────────────────────────────────────────────
    # MUST come AFTER os.chdir — STATE_FILE is relative ("./pytest_reboot_state.json")
    cls.reboot_mgr = RebootManager(total_tests=cls._count_test_methods())

    phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
    logger.info(f"[SETUP] Phase: {phase}")
    logger.info(f"[SETUP] Test case: {testcase_config.case_id}  version: {testcase_config.case_version}")
    logger.info(f"[SETUP] Working directory: {test_dir}")

    # ── 4. RunCard ────────────────────────────────────────────────────
    cls._init_runcard(runcard_params)
    # Non-fatal: cls.runcard is set to None if RunCard init fails

    yield   # ← all test_XX methods execute here

    # ── 5. Teardown: RunCard ─────────────────────────────────────────
    cls._teardown_runcard(request.session)
    # Calls runcard.end_test(PASS/FAIL) based on session.testsfailed; no-op if cls.runcard is None

    # ── 6. Teardown: RebootManager ───────────────────────────────────
    cls._teardown_reboot_manager()
    # Calls reboot_mgr.cleanup() — removes state file + Startup BAT; swallows all exceptions

    # ── 7. Restore working directory ─────────────────────────────────
    logger.info(f"{cls.__name__} session complete")
    os.chdir(cls.original_cwd)
```

> **If the test class has teardown-specific logic** (e.g., reverting OS changes), insert it between steps 5 and 6:
> ```python
> if cls._osconfig_controller is not None:
>     try:
>         cls._osconfig_controller.revert_all()
>     except Exception as exc:
>         logger.warning(f"[TEARDOWN] OsConfig revert failed — {exc} (continuing)")
> ```

---

### BaseTestCase Helper Methods Reference

| Method | Where to call | What it does |
|--------|--------------|--------------|
| `cls._setup_working_directory(__file__)` | start of setup | Resolves test dir, `os.chdir()`, calls `logConfig()`; returns resolved `Path` |
| `cls._count_test_methods()` | `RebootManager(total_tests=...)` | Counts methods starting with `test_` on the class; used so `all_tests_completed()` works correctly |
| `cls._init_runcard(runcard_params)` | after RebootManager | Non-fatal RunCard start; sets `cls.runcard` (`None` on error) |
| `cls._teardown_runcard(request.session)` | teardown before cleanup | Calls `runcard.end_test(PASS/FAIL)`; no-op when `cls.runcard is None` |
| `cls._teardown_reboot_manager()` | teardown last step | Calls `reboot_mgr.cleanup()`, swallows exceptions |

---

### Per-Test-Case `conftest.py` Requirements

Each test case must provide two fixtures in its local `conftest.py`:

**1. `testcase_config` (session scope)**
```python
@pytest.fixture(scope="session")
def testcase_config():
    case_root_dir = Path(__file__).parent
    config = TestCaseConfiguration(case_root_dir)
    # Optional: override defaults
    config.smicli_executable = case_root_dir / "bin/SmiWinTools/bin/x64/SmiCli2.exe"
    return config
```
`TestCaseConfiguration` auto-infers `case_id` from the directory name (`stc<N>_xxx` → `STC-N`), loads `Config/Config.json`, and resolves `bin_directory`.

**2. `test_params` (session scope, optional but recommended)**  
Define a `@dataclass` with all tunable thresholds/durations, then expose it as a fixture:
```python
@dataclass
class STC2562Params:
    wake_after_min: int = 60
    sleepstudy_threshold: int = 90
    drips_threshold: int = 80

@pytest.fixture(scope="session")
def test_params() -> STC2562Params:
    return STC2562Params()
```
Test methods that need thresholds declare `test_params` as a parameter:
```python
def test_07_verify_sleepstudy(self, test_params):
    threshold = test_params.sleepstudy_threshold
```

---

### Initialisation Order Rules

| Order | Rule | Reason |
|-------|------|--------|
| 1st | `_setup_working_directory(__file__)` before everything else | All subsequent relative paths (`Config.json`, state file, `testlog/`) depend on cwd |
| 2nd | `cls.config = testcase_config.tool_config` before `RebootManager` | RebootManager init itself doesn't need config, but subsequent log messages do |
| 3rd | `RebootManager(total_tests=cls._count_test_methods())` after `os.chdir` | `STATE_FILE = "./pytest_reboot_state.json"` is relative to cwd |
| 4th | `_init_runcard(runcard_params)` after RebootManager | RunCard logging is non-blocking; order relative to RunCard is flexible |
| Teardown: last | `os.chdir(original_cwd)` | Must be absolute last — restores cwd for any code that runs after this fixture |

---

## RebootManager Usage in Test Cases

`framework/reboot_manager.py` (`RebootManager`) provides **cross-reboot pytest session recovery**.
When a test needs to reboot the machine and then continue with the next step, `RebootManager` persists which steps have already completed, installs a Startup-folder BAT that re-launches pytest after reboot, and provides guards so that completed steps are skipped automatically on resume.

> **Reference implementation**: `tests/integration/client_pcie_lenovo_storagedv/stc2562_modern_standby/test_main.py`  
> **Auto-skip mechanism**: `framework/base_test.py` — `BaseTestCase.setup_teardown_function` calls `reboot_mgr.is_completed(test_name)` and `pytest.skip()` for every test before it executes.

---

### Key API

| Method | When to call | Notes |
|--------|-------------|-------|
| `RebootManager(total_tests=N)` | fixture setup | N = total number of `@pytest.mark.order(N)` steps |
| `is_recovering()` | fixture setup (log phase) | `True` if this is a post-reboot resume |
| `pre_mark_completed(request.node.name)` | **inside the reboot test step** | Must call BEFORE `setup_reboot()` — see pitfall below |
| `setup_reboot(delay, reason, test_file)` | inside the reboot test step | Increments `reboot_count`, writes Startup BAT, calls `os._exit(0)` |
| `require_after(predecessor)` | first line of post-reboot steps | **Preferred** — guards by predecessor test name, not a magic counter |
| `require_rebooted(min_count=N)` | first line of post-reboot steps | Alternative — use only when no single predecessor name makes sense |
| `reboot_cycles(count, *, request, test_file, delay, reason)` | inside a step that needs N reboots | Returns normally after Nth reboot; `pre_mark_completed` is **not** needed — handled internally |
| `loop_next(group, *, total, steps, request, test_file, reboot, delay, reason)` | last step of a repeating block | Clears `completed_tests` for `steps` and reboots after each non-final round; returns on final round |
| `cleanup()` | fixture teardown | Removes state file + Startup BAT |

---

### Pattern 1 — Fixture Initialization

Always initialize `RebootManager` after `os.chdir()` to the test directory (state file path is relative to cwd):

```python
@pytest.fixture(scope="class", autouse=True)
def setup_test_class(self, request, testcase_config, runcard_params):
    cls = request.cls
    os.chdir(test_dir)   # ← must happen BEFORE RebootManager()

    # ── Initialize RebootManager ─────────────────────────────────────
    cls.reboot_mgr = RebootManager(total_tests=13)

    phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
    logger.info(f"[SETUP] Phase: {phase}")

    yield

    # ── Teardown: cleanup state file + Startup BAT ───────────────────
    try:
        cls.reboot_mgr.cleanup()
    except Exception as exc:
        logger.warning(f"[TEARDOWN] RebootManager cleanup failed — {exc}")
```

---

### Pattern 2 — Reboot Step (Pre-Reboot side)

Any test step that needs to reboot must:
1. Do its work first (e.g., clear history, install something).
2. Call `pre_mark_completed(request.node.name)` **before** `setup_reboot()`.
3. Call `setup_reboot()` — this returns only via `os._exit(0)`, so no code after it runs.

```python
@pytest.mark.order(5)
@step(5, "Clear Sleep Study history & Reboot device")
def test_05_clear_sleep_history(self, request):
    # ... do any pre-reboot work ...

    # ① Mark this step done so it won't re-execute after reboot
    self.reboot_mgr.pre_mark_completed(request.node.name)

    # ② Schedule reboot; os._exit(0) is called internally — nothing after this runs
    self.reboot_mgr.setup_reboot(
        delay=10,
        reason="Phase A complete — rebooting before PwrTest",
        test_file=__file__,   # ← tells the Startup BAT which file to re-run
    )
    # ← code here is unreachable
```

> **Why `pre_mark_completed` is required**: `setup_reboot()` calls `os._exit(0)`, bypassing
> pytest's teardown. Without pre-marking, `BaseTestCase.setup_teardown_function` never reaches
> `reboot_mgr.mark_completed()`, so the reboot step appears incomplete after resume and would
> execute again → **infinite reboot loop**.

---

### Pattern 3 — Post-Reboot Step (Hard Guard)

Steps that must only run *after* a specific predecessor prefer `require_after(predecessor_name)`.
This is more robust than a magic `min_count` number — if steps are added or removed, only the name needs updating.

```python
@pytest.mark.order(10)
@step(10, "PHM collector — run Modern Standby")
def test_10_run_modern_standby(self):
    # Preferred: guard by predecessor name rather than hardcoded reboot count.
    # test_09 is pre_mark_completed before the 2nd reboot, so this implicitly
    # asserts that both reboots have occurred.
    self.reboot_mgr.require_after("test_09_clear_sleepstudy_and_reboot")
    # ... rest of step ...
```

Use `require_rebooted(min_count=N)` only when there is no single named predecessor that cleanly
expresses the phase boundary (rare).

---

### Pattern 4 — Consecutive Reboots (`reboot_cycles`)

Use `reboot_cycles()` when a single test step needs to perform **N reboots in a row** and
then continue.  The method handles all bookkeeping internally — no `pre_mark_completed` call is
needed from the test body.

```python
@pytest.mark.order(2)
@step(2, "Reboot device N times")
def test_02_reboot_cycles(self, request):
    # Performs 3 reboots.  Each time pytest resumes, steps 01..01 are
    # skipped (already in completed_tests).  This step re-enters and
    # increments its per-step counter until it reaches 3, then returns.
    self.reboot_mgr.reboot_cycles(
        3,
        request=request,
        test_file=__file__,           # ← required: tells Startup BAT which file to re-run
        delay=10,                     # seconds before shutdown (default 10)
        reason="Pre-condition: cycling device power",
    )
    # Execution reaches here only after 3 successful reboots.
    logger.info("[TEST_02] All 3 reboots completed — continuing with next step")
```

**How it works internally**:
- Maintains a `step_reboot_counts[step_name]` counter in the state file.
- If `current_count < count`: increments counter, calls `setup_reboot()` (→ `os._exit(0)`).
- If `current_count >= count`: removes the per-step counter, returns normally.
- `BaseTestCase.setup_teardown_function` marks the step completed **after** `reboot_cycles` returns.

---

### Pattern 5 — Repeating Loop (`loop_next`)

Use `loop_next()` when a **block of steps** must execute multiple times (rounds), with an
optional reboot between rounds.  Call it at the **end of the last step** in the block.

```python
# Example: steps test_02, test_03, test_04 must repeat 3 times.

@pytest.mark.order(2)
@step(2, "Step A")
def test_02_step_a(self):
    logger.info("[TEST_02] Step A running (will repeat each round)")

@pytest.mark.order(3)
@step(3, "Step B")
def test_03_step_b(self):
    logger.info("[TEST_03] Step B running")

@pytest.mark.order(4)
@step(4, "End of loop — advance to next round")
def test_04_end_of_loop(self, request):
    logger.info("[TEST_04] End-of-loop reached")

    self.reboot_mgr.loop_next(
        "main_loop",                              # unique name for this loop
        total=3,                                  # total rounds to execute
        steps=[                                   # step names cleared between rounds
            "test_02_step_a",
            "test_03_step_b",
            "test_04_end_of_loop",
        ],
        request=request,
        test_file=__file__,                       # required when reboot=True
        reboot=True,                              # reboot between rounds (default True)
        delay=10,
        reason="Loop round complete — rebooting for next round",
    )
    # Reached here only after the FINAL round — test_05 follows.
    logger.info("[TEST_04] All 3 rounds complete — proceeding to test_05")
```

**How it works internally**:
- Maintains a `loop_groups[group]` dict with `current_round` in the state file.
- On each non-final round: increments `current_round`, removes listed steps from
  `completed_tests`, then calls `setup_reboot()` (or returns when `reboot=False`).
- On the final round: removes the group entry from state and returns normally.
- Because the loop steps are removed from `completed_tests`, pytest re-runs them
  in the next session; steps **outside** the loop are still skipped.

**`reboot=False` variant** — use when no reboot is needed between repetitions but the
same pytest session should re-run the block immediately:

```python
self.reboot_mgr.loop_next(
    "validation_loop",
    total=5,
    steps=["test_03_check", "test_04_validate"],
    request=request,
    reboot=False,   # no reboot — same session continues; pytest re-runs cleared steps
)
```

---

### Multi-Reboot Flow (Two Reboots Example)

```
─── PRE-REBOOT (reboot_count=0) ─────────────────────────────────────────────
  test_01 → runs → marked completed
  test_02 → runs → marked completed
  ...
  test_05 → pre_mark_completed("test_05_...")
           setup_reboot(delay=10, test_file=__file__)
           [os._exit(0) — process terminates]
  [SYSTEM REBOOTS — Startup BAT re-launches pytest]

─── POST-REBOOT 1 (reboot_count=1) ──────────────────────────────────────────
  test_01..05 → skipped (already in completed_tests)
  test_06 → runs → marked completed
  ...
  test_09 → pre_mark_completed("test_09_...")
            setup_reboot(...)
            [os._exit(0)]
  [SYSTEM REBOOTS AGAIN — Startup BAT re-launches pytest]

─── POST-REBOOT 2 (reboot_count=2) ──────────────────────────────────────────
  test_01..09 → skipped (already in completed_tests)
  test_10 → require_rebooted(min_count=2)  ← guards against wrong phase
             ... runs ...
  test_11..13 → run sequentially
  [teardown: reboot_mgr.cleanup() removes state file + BAT]
```

---

### Rules & Pitfalls

| Rule | Reason |
|------|--------|
| Call `pre_mark_completed()` **before** `setup_reboot()` | `os._exit(0)` bypasses pytest teardown — no other chance to persist the completed flag |
| Always pass `test_file=__file__` to `setup_reboot()` and `reboot_cycles()` | The Startup BAT needs the path to re-run the correct test file |
| `os.chdir()` must happen before `RebootManager()` | `STATE_FILE` path is relative (`"./pytest_reboot_state.json"`) |
| Prefer `require_after(predecessor)` over `require_rebooted(min_count=N)` | Name-based guard is self-documenting and doesn't break when steps are added/removed |
| Use `require_rebooted(min_count=N)` only as fallback | Only when no single predecessor name cleanly expresses the phase boundary |
| Do **not** call `pre_mark_completed()` when using `reboot_cycles()` | `reboot_cycles()` manages its own counter; adding a manual `pre_mark_completed` causes the step to be skipped before the cycles finish |
| Pass **all** repeating step names to `loop_next(steps=[...])` | Only listed steps are removed from `completed_tests`; omitting a step means it stays skipped in subsequent rounds |
| Do **not** call `reboot_mgr.cleanup()` inside the reboot step | Cleanup must only happen in teardown after all tests complete normally |
| `total_tests` must equal the actual number of `@pytest.mark.order(N)` steps | Used by `all_tests_completed()` to decide when to clean up |

---

## Important Notes

- Always import logger with `from lib.logger import get_module_logger`
- All controllers must be thread-safe: use `threading.Event` for stop signals
- `status` property returns `None` while running, `True` on pass, `False` on fail
- Use `sys.path.insert(0, str(Path(__file__).parent.parent.parent))` for imports
- Config validation should raise `<Tool>ConfigError`, not generic exceptions
- pywinauto imports must be wrapped in `try/except ImportError` for testability
