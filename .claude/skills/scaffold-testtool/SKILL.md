---
name: scaffold-testtool
description: Scaffold a new testtool library sub-package under lib/testtool/ using the burnin package as the standard template. Use when user asks to create a new testtool, add a library for a tool, migrate a legacy single-file testtool, scaffold a testtool package, or mentions 建 testtool, 新增工具 library, 遷移, or wrapping a CLI/GUI/BAT tool.
---

# Scaffold Testtool Library Skill

Generate a new `lib/testtool/<toolname>/` sub-package following the standard architecture defined by `lib/testtool/burnin/`.

## Standard Package Structure

Every testtool library follows this layout:

```
lib/testtool/<toolname>/
├── __init__.py          # Package entry, exports, docstring with usage example
├── config.py            # DEFAULT_CONFIG, type validation, merge_config()
├── controller.py        # Main controller (inherits threading.Thread)
├── exceptions.py        # Exception hierarchy (Base → sub-classes)
├── process_manager.py   # Install/Start/Stop/Kill lifecycle  [optional]
├── script_generator.py  # Script/config file generation      [optional]
└── ui_monitor.py        # pywinauto UI automation            [optional]
```

Optional modules are only created when the tool spec requires them:
- `process_manager.py` → when `requires_install: true`
- `script_generator.py` → when `has_script_generator: true`
- `ui_monitor.py` → when `has_ui: true`

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
3. `controller.py` — main threading controller
4. `process_manager.py` — (if `requires_install: true`)
5. `script_generator.py` — (if `has_script_generator: true`)
6. `ui_monitor.py` — (if `has_ui: true`)
7. `__init__.py` — exports + usage docstring

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
└── test_controller.py    # unittest style — mocked dependencies, init/status/stop/run
```

Optional (create only if the corresponding module exists):
- `test_process_manager.py` — if `requires_install: true`
- `test_script_generator.py` — if `has_script_generator: true`
- `test_ui_monitor.py` — if `has_ui: true`

**Key rules:**
- `test_exceptions.py` / `test_config.py` → use **pytest** class style
- `test_controller.py` → use **unittest.TestCase** style with `setUp` / `tearDown`
- **Never** call real executables or touch the real file system — mock everything
- Patch `pathlib.Path.exists`, `subprocess.Popen`, sub-components as needed
- `status` property: assert `None` before `start()`, `True`/`False` after `join()`
- Shared fixtures go in `conftest.py`; adapt `sample_config` to tool's required params

**For complete templates and examples**, see `references/test_templates.md`

### Step 4 — Verify

After generating:
```powershell
# Check for syntax errors
python -m py_compile lib/testtool/<package_name>/*.py

# Run generated tests
python -m pytest tests/unit/lib/<package_name>/ -v
```

---

## Module Generation Rules

### `exceptions.py`

Always generate these base exceptions. Add tool-specific ones based on the spec:

```python
class <Tool>Error(Exception): ...          # always
class <Tool>ConfigError(<Tool>Error): ...  # always
class <Tool>TimeoutError(<Tool>Error): ... # always
class <Tool>ProcessError(<Tool>Error): ... # always
class <Tool>InstallError(<Tool>Error): ... # only if requires_install: true
class <Tool>UIError(<Tool>Error): ...      # only if has_ui: true
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

## Related Files

- **Template Reference**: `lib/testtool/burnin/` — canonical example package
- **Secondary Template**: `lib/testtool/smartcheck/` — simpler example (no UI, no install)
- **Unit Test Reference**: `tests/unit/lib/testtool/test_burnin/` — canonical test suite
- **Logger**: `lib/logger.py` — use `get_module_logger(__name__)` in all modules
- **Test Base**: `framework/base_test.py` — for integration test scaffolding
- **Full Schema**: `.claude/skills/scaffold-testtool/references/tool_spec_schema.md`
- **Burnin Example**: `.claude/skills/scaffold-testtool/references/burnin_example.md`
- **Module Templates**: `.claude/skills/scaffold-testtool/references/module_templates.md`
- **Test Templates**: `.claude/skills/scaffold-testtool/references/test_templates.md`

## Important Notes

- Always import logger with `from lib.logger import get_module_logger`
- All controllers must be thread-safe: use `threading.Event` for stop signals
- `status` property returns `None` while running, `True` on pass, `False` on fail
- Use `sys.path.insert(0, str(Path(__file__).parent.parent.parent))` for imports
- Config validation should raise `<Tool>ConfigError`, not generic exceptions
- pywinauto imports must be wrapped in `try/except ImportError` for testability
