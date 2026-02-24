# BurnIN — Complete Worked Example

This is the ground-truth example. `lib/testtool/burnin/` is the canonical implementation of the scaffold-testtool pattern.

## Tool Spec (Reconstructed)

```yaml
tool:
  name: "BurnIn"
  package_name: "burnin"
  description: "PassMark BurnInTest wrapper for disk burn-in testing"
  version: "2.0.0"

execution:
  type: "gui"
  executable: "bit.exe"
  requires_install: true
  has_ui: true
  has_script_generator: true

config_params:
  - name: "installer_path"
    type: "str"
    default: ""
    description: "Path to BurnIN installer"
  - name: "license_path"
    type: "str"
    default: ""
    description: "Optional license key file path"
  - name: "install_path"
    type: "str"
    default: "C:\\Program Files\\BurnInTest"
    description: "Installation directory"
  - name: "executable_name"
    type: "str"
    default: "bit.exe"
    description: "Executable name (bit.exe or bit64.exe)"
  - name: "script_path"
    type: "str"
    default: "./Config/BIT_Config/BurnInScript.bits"
    description: "Path to .bits script file"
  - name: "config_file_path"
    type: "str"
    default: "./Config/BIT_Config/BurnInScript.bitcfg"
    description: "Path to .bitcfg config file"
  - name: "test_duration_minutes"
    type: "int"
    default: 1440
    description: "Test duration in minutes (24h default)"
  - name: "test_drive_letter"
    type: "str"
    default: "D"
    description: "Drive letter to test"
  - name: "log_path"
    type: "str"
    default: "./testlog/Burnin.log"
    description: "Log output path"
  - name: "timeout_minutes"
    type: "int"
    default: 100
    description: "Execution timeout in minutes"
  - name: "check_interval_seconds"
    type: "float"
    default: 2.0
    description: "Status check interval"
  - name: "ui_retry_max"
    type: "int"
    default: 60
    description: "Maximum UI connection retries"
  - name: "enable_screenshot"
    type: "bool"
    default: true
    description: "Enable screenshot capture"
  - name: "screenshot_path"
    type: "str"
    default: "./testlog/screenshots"
    description: "Screenshot output directory"

result_parsing:
  method: "ui"
  pass_pattern: "Test Finished"
  fail_pattern: "error_count > 0"

exceptions:
  - "InstallError"
  - "UIError"
  - "TestFailedError"
```

---

## File-by-File Implementation Notes

### `exceptions.py`
- 7 exception classes total
- `BurnInError` → base
- `BurnInConfigError`, `BurnInTimeoutError`, `BurnInProcessError` → always
- `BurnInInstallError` → because `requires_install: true`
- `BurnInUIError` → because `has_ui: true`
- `BurnInTestFailedError` → always
- See `lib/testtool/burnin/exceptions.py` (118 lines)

### `config.py`
- `BurnInConfig` class (no inheritance)
- All keys from spec in `DEFAULT_CONFIG`
- `VALID_PARAMS = set(DEFAULT_CONFIG.keys())`
- `PARAM_TYPES` covers every key with Python type(s) — use tuple `(int, float)` for numeric fields that accept both
- `get_default_config()` returns `copy.deepcopy(DEFAULT_CONFIG)`
- `validate_config()` checks type, required fields, returns `bool` and logs warnings
- `merge_config()` returns `{**base, **overrides}` after validation
- See `lib/testtool/burnin/config.py` (251 lines)

### `controller.py`
- `BurnInController(threading.Thread)` — 999 lines, most complex file
- `__init__` accepts all config_params as keyword args with defaults from `BurnInConfig.DEFAULT_CONFIG`
- Internal state: `_config`, `_stop_event (threading.Event)`, `_status`, `_error_count`
- `set_config(**kwargs)` validates and updates config at runtime
- `is_installed()` → delegates to `BurnInProcessManager`
- `install()`, `uninstall()` → delegates to `BurnInProcessManager`
- `run()` → calls `_execute_test()` which orchestrates: script generation → process start → UI monitoring → result collection
- `stop()` → sets `_stop_event`
- `status` property → `None` while running, `True`/`False` after completion
- `error_count` property → int
- See `lib/testtool/burnin/controller.py`

### `process_manager.py`
- `BurnInProcessManager` class (not a Thread)
- `__init__(install_path, executable_name="bit.exe")`
- `is_installed() -> bool` — checks if executable exists at `install_path`
- `install(installer_path, license_path=None) -> None` — runs installer silently
- `uninstall() -> None` — runs uninstaller
- `start_process(script_path) -> subprocess.Popen` — launches `bit.exe -S script -K -R`
- `stop_process() -> None` — terminates process by PID
- `kill_process() -> None` — force-kills via `psutil`
- `is_running() -> bool` — checks PID is alive
- See `lib/testtool/burnin/process_manager.py` (607 lines)

### `script_generator.py`
- `BurnInScriptGenerator` — all static methods, never instantiated
- `generate_disk_test_script(config_file_path, log_path, duration_minutes, drive_letter, output_path) -> str`
  - Writes a `.bits` XML/text script file
  - Returns the `output_path`
- See `lib/testtool/burnin/script_generator.py` (233 lines)

### `ui_monitor.py`
- `BurnInUIMonitor` class (not a Thread)
- Uses `pywinauto` — import wrapped in `try/except ImportError`
- `__init__(window_title, retry_max, retry_interval)`
- `connect() -> bool` — tries to connect to the BurnIN window
- `read_status() -> str` — reads status text from UI element
- `get_error_count() -> int` — reads error count from UI
- `handle_dialogs() -> None` — auto-dismisses known dialogs (license, warnings)
- `capture_screenshot(path) -> str` — saves screenshot, returns path
- `disconnect() -> None`
- See `lib/testtool/burnin/ui_monitor.py` (646 lines)

### `__init__.py`
```python
"""
BurnIN Package
...
Usage:
    from lib.testtool.burnin import BurnInController
    controller = BurnInController(
        install_path="C:\\Program Files\\BurnInTest",
        installer_path="./bin/BurnIn/bitwindows.exe",
        license_path="./bin/BurnIn/key.dat"
    )
    controller.set_config(test_duration_minutes=60, test_drive_letter='D')
    controller.start()
    controller.join(timeout=7200)
    if controller.status:
        print("BurnIN test PASSED")
"""
from .controller import BurnInController
from .config import BurnInConfig
from .exceptions import (BurnInError, BurnInConfigError, BurnInTimeoutError,
                          BurnInProcessError, BurnInInstallError,
                          BurnInUIError, BurnInTestFailedError)
__version__ = '2.0.0'
__all__ = ['BurnInController', 'BurnInConfig', 'BurnInError', ...]
```

---

## Comparison: Legacy vs New Architecture

| Aspect | `lib/testtool/BurnIN.py` (legacy) | `lib/testtool/burnin/` (new) |
|--------|----------------------------------|------------------------------|
| Structure | Single monolithic class | 7 focused modules |
| Threading | None | `threading.Thread` |
| Config | `setattr` from dict | `BurnInConfig` with validation |
| Error handling | No custom exceptions | 7-level exception hierarchy |
| Testability | Hard to mock | Each module independently testable |
| Type hints | None | Full type annotations |
| Logging | Mixed `print` / logger | `get_module_logger(__name__)` throughout |
| Install | Mixed into main class | Isolated in `BurnInProcessManager` |
| UI monitoring | Inline in main class | Isolated in `BurnInUIMonitor` |

## Usage in Integration Tests

```python
# tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin/
from lib.testtool.burnin import BurnInController

class TestBurnIn(BaseTestCase):
    def test_burn_in(self):
        controller = BurnInController(
            install_path=self.config['burnin_install_path'],
            installer_path=self.config['burnin_installer'],
        )
        controller.set_config(
            test_duration_minutes=self.config.get('duration', 60),
            test_drive_letter=self.config.get('drive', 'D'),
        )
        controller.start()
        controller.join(timeout=controller.timeout_seconds)
        self.assertTrue(controller.status, f"BurnIN failed with {controller.error_count} errors")
```
