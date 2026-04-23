# WinPVT Tool Reference

**Package location**: `lib/testtool/winpvt/`
**Chocolatey package**: `bin/chocolatey/packages/winpvt/`
**Install path**: `C:\Program Files\Hewlett-Packard\WinPVT 11.16.0`
**Key binary**: `C:\Program Files\Hewlett-Packard\WinPVT 11.16.0\WinPVT.exe`
**Default exe (WinPVTConfig)**: `C:\Program Files\Hewlett-Packard\WinPVT 11.16.0\WinPVT.exe`

---

## Overview

HP WinPVT is a GUI-based SSD stress test tool for Windows. It requires:
- **pywinauto** for UI automation (backend: `uia`)
- **psutil** for process liveness checks
- **Pillow** for optional screenshots (`WINPVT_DEBUG_SCREENSHOTS=1`)

`WinPVTController` is a `threading.Thread` subclass with a two-phase API:

| Phase | Method | What it does |
|-------|--------|-------------|
| Phase 1 (sync) | `ctrl.setup_phase()` | Launch WinPVT.exe, wait for main window, dismiss all startup dialogs |
| Phase 2 (thread) | `ctrl.start()` + `ctrl.join()` | Open `.pvt` file, click GO, wait for Test Summary dialog / Status=Completed, read cycles |

---

## Package Structure

```
lib/testtool/winpvt/
├── __init__.py          # exports WinPVTController, WinPVTConfig, WinPVTUIMonitor, exceptions
├── controller.py        # WinPVTController (threading.Thread)
├── config.py            # WinPVTConfig — defaults, validation, merge
├── ui_monitor.py        # WinPVTUIMonitor — screenshots, dialog dismissal, topology logging
├── exceptions.py        # WinPVTError hierarchy
└── package_meta.yaml    # choco_package_id: winpvt, version: 11.16.0
```

---

## Controller API

```python
from lib.testtool.winpvt import WinPVTController, WinPVTConfig
from lib.testtool.winpvt.exceptions import WinPVTError

# Instantiate (keyword args override defaults)
ctrl = WinPVTController(
    exe_path=r'C:\Program Files\Hewlett-Packard\WinPVT 11.16.0\WinPVT.exe',
    result_path='./testlog/WinPVTResult',
    test_category='Standby',
    stress_level='Critical',
    timeout_minutes=800,
    pvt_file=r'C:\...\Standby Critical Only.pvt',   # or relative path resolved below
    screenshot_dir='./testlog/WinPVTScreenshots',
)

# Phase 1: launch + dismiss startup dialogs (synchronous, in test step)
try:
    ctrl.setup_phase()
except WinPVTError as exc:
    pytest.fail(f"WinPVT startup failed: {exc}")

# Phase 2: open .pvt, click GO, wait for completion (threaded)
ctrl.start()
ctrl.join(timeout=ctrl.timeout_seconds + 120)   # extra 120s grace

if ctrl.is_alive():
    ctrl.stop()
    pytest.fail("WinPVT timed out")

if ctrl.status is not True:
    pytest.fail(f"WinPVT failed: {ctrl.error_message}")

# Read completed cycles (available after join)
cycles = ctrl.cycles   # int; read from WinPVT StatusBar "Cycles: XXXXXXXX"

# Explicit close (WinPVT does NOT self-terminate)
ctrl.close_app()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `status` | `None / True / False` | `None` while running; `True` = PASS; `False` = FAIL |
| `error_message` | `str` | Human-readable reason for failure (empty on success) |
| `cycles` | `int` | Completed standby cycles read from StatusBar; 0 if not found |
| `timeout_seconds` | `int` | `timeout_minutes * 60`; used in `ctrl.join(timeout=...)` |

---

## WinPVTConfig — All Parameters

| Key | Default | Description |
|-----|---------|-------------|
| `exe_path` | `C:\Program Files\Hewlett-Packard\WinPVT 11.16.0\WinPVT.exe` | Path to WinPVT.exe |
| `result_path` | `./testlog/WinPVTResult` | Directory where WinPVT writes result files |
| `screenshot_dir` | `./testlog/WinPVTScreenshots` | Directory for UI screenshots |
| `test_category` | `Standby` | Test category to run |
| `stress_level` | `Critical` | Stress level |
| `timeout_minutes` | `120` | Max minutes to wait for WinPVT completion (Phase 2) |
| `pvt_file` | `C:\...\Standby Critical Only.pvt` | Absolute path to `.pvt` test plan file |
| `dialog_dismiss_timeout` | `120` | Max seconds for startup dialog dismissal loop (Phase 1) |
| `window_wait_timeout` | `30` | Max seconds to wait for main window after launch (Phase 1) |

---

## Exception Hierarchy

```
WinPVTError                  # base
├── WinPVTConfigError        # bad config param or type
├── WinPVTProcessError       # exe not found, launch failure, process exited unexpectedly
├── WinPVTTimeoutError       # test did not complete within timeout_minutes
├── WinPVTUIError            # pywinauto window/button not found, dialog fill failed
└── WinPVTTestFailedError    # WinPVT reported errors > 0 in results
```

Catch `WinPVTError` as the base in test steps; log `exc` and call `pytest.fail()`.

---

## .pvt File — Test Plan

WinPVT runs a test plan loaded from a `.pvt` file:

- **Default** (installed with WinPVT): `C:\Program Files\Hewlett-Packard\WinPVT 11.16.0\Test Plans\Power Management\Standby Critical Only.pvt`
- **Custom**: Store in `Config/` alongside `Config.json`; reference in `Config.json` as a relative path

### Relative Path Resolution Pattern

```python
pvt_file = winpvt_cfg.get('PvtFile', '').strip()
if pvt_file:
    pvt_path = Path(pvt_file)
    if not pvt_path.is_absolute():
        pvt_path = Path(__file__).parent / pvt_path   # resolve from test case dir
    ctrl_kwargs['pvt_file'] = str(pvt_path)
```

If `PvtFile` is omitted from Config.json, `WinPVTConfig.DEFAULT_CONFIG['pvt_file']`
(the installed default) is used automatically.

---

## Config.json Section

```json
"winpvt": {
    "LogPath":          "./testlog/WinPVTLog",
    "ResultPath":       "./testlog/WinPVTResult",
    "test_category":    "Standby",
    "stress_level":     "Critical",
    "timeout_minutes":  800,
    "PvtFile":          "Config/winpvt_prod.pvt"
}
```

`ExePath` is optional — omit to use the installed default. Pass it only when the binary
is in a non-standard location.

---

## tools.yaml Entry

```yaml
tools:
  - id: winpvt
    reinstall: false
    phase: test   # install in test_02_install_tools, not pre_runcard
```

> **Why `phase: test`?** WinPVT is a large GUI installer; installing it in
> `setup_test_class` (pre_runcard) adds unnecessary overhead. Install it explicitly
> in `test_02_install_tools` instead.

---

## Two-Phase Test Step Pattern (canonical: stc1067)

```python
# Step N: WinPVT Startup — Phase 1 (synchronous)
@pytest.mark.order(N)
@step(N, "WinPVT Startup: launch and dismiss dialogs")
def test_0N_winpvt_startup(self):
    # Kill stale process from previous interrupted run
    import subprocess
    result = subprocess.run(['taskkill', '/F', '/IM', 'WinPVT.exe'], capture_output=True)
    if result.returncode == 0:
        logger.info("[TEST_0N] Killed stale WinPVT.exe")

    winpvt_cfg = self.config['winpvt']
    ctrl_kwargs = dict(
        exe_path=winpvt_cfg.get('ExePath') or WinPVTConfig.DEFAULT_CONFIG['exe_path'],
        result_path=winpvt_cfg['ResultPath'],
        test_category=winpvt_cfg.get('test_category', 'Standby'),
        stress_level=winpvt_cfg.get('stress_level', 'Critical'),
        timeout_minutes=winpvt_cfg.get('timeout_minutes', 120),
        screenshot_dir='./testlog/WinPVTScreenshots',
    )
    pvt_file = winpvt_cfg.get('PvtFile', '').strip()
    if pvt_file:
        pvt_path = Path(pvt_file)
        if not pvt_path.is_absolute():
            pvt_path = Path(__file__).parent / pvt_path
        ctrl_kwargs['pvt_file'] = str(pvt_path)

    ctrl = WinPVTController(**ctrl_kwargs)
    try:
        ctrl.setup_phase()
    except WinPVTError as exc:
        pytest.fail(f"[TEST_0N] WinPVT startup failed: {exc}")

    TestSTC<XXXX>._winpvt_ctrl = ctrl   # share with next step

# Step N+1: Run WinPVT — Phase 2 (threaded)
@pytest.mark.order(N+1)
@step(N+1, "Run WinPVT Standby Critical")
def test_0M_run_winpvt(self):
    ctrl = TestSTC<XXXX>._winpvt_ctrl
    if ctrl is None:
        pytest.fail("[TEST_0M] WinPVT controller not initialised — test_0N may have failed")

    ctrl.start()
    ctrl.join(timeout=ctrl.timeout_seconds + 120)

    if ctrl.is_alive():
        ctrl.stop()
        pytest.fail(f"[TEST_0M] WinPVT timed out")

    if ctrl.status is not True:
        pytest.fail(f"[TEST_0M] WinPVT failed: {ctrl.error_message}")

    # Update RunCard with cycle count
    cycles = ctrl.cycles
    if self.runcard is not None and cycles > 0:
        self.runcard.update_test_status(test_cycle=cycles)
        self.runcard.save_to_file()

    # Close WinPVT (does NOT self-terminate)
    ctrl.close_app()
```

---

## Completion Detection Strategy

`_wait_for_completion()` polls every 5 seconds using three checks (in priority order):

1. **Test Summary dialog** — modal dialog titled `"Test Summary"` appears when the test ends.
   Controller screenshots it, parses Errors from the Global Information table, clicks OK.
2. **Global Information table** — scans `ListItem` descendants for `Status='Completed'`.
   Used as a fallback when the Test Summary dialog is missed.
3. **Process exit** — if the WinPVT process exits unexpectedly (crash), polling stops.

Pass/fail is always determined by `Errors > 0` in the table, not dialog text, so
tests that complete with Warnings are not misreported as FAIL.

---

## Screenshots

| Label | When captured | Condition |
|-------|--------------|-----------|
| `launch_main_window` | After main window appears | debug only |
| `after_dialogs_cleared` | After all startup dialogs dismissed | debug only |
| `after_test_plan_loaded` | After .pvt file loaded | debug only |
| `after_go_clicked` | After Run button clicked | debug only |
| `final_state` | Always — at end of wait loop | **always** |
| `timeout_final` | On timeout before raising WinPVTTimeoutError | always |

Set `WINPVT_DEBUG_SCREENSHOTS=1` env var to enable debug-only screenshots.

---

## Known Behaviour / Pitfalls

### Two separate steps for Phase 1 and Phase 2
`setup_phase()` (Phase 1) must run in its own test step so its `pytest.fail()` is
independently tracked and reported. If combined into one step, Phase 1 failure silently
skips Phase 2. Split into `test_0N_winpvt_startup` + `test_0M_run_winpvt`.

### Shared class variable for ctrl
`_winpvt_ctrl` must be a **class-level** variable (not instance-level) so the startup
step can pass it to the run step. Declare at class level:
```python
_winpvt_ctrl: "WinPVTController | None" = None
```

### Pre-run dialog flush (residual late dialogs)
After `setup_phase()` returns, WinPVT may show additional dialogs (e.g., "No AccessKey.txt"
popup) a few seconds later. `_run_test_phase()` runs a second 30-second dialog flush before
opening the test plan. This is automatic and requires no test-step changes.

### taskkill /F /T on close_app()
`close_app()` first tries `Alt+F4`, then `taskkill /F /T /PID` to kill the entire process
tree (WinPVT spawns child processes for dialogs). Finally it falls back to
`taskkill /F /IM WinPVT.exe` as a safety net. Always call `close_app()` after the run step.

### WinPVT does NOT self-terminate
After displaying the Test Summary dialog and clicking OK, WinPVT remains open. The test step
must call `ctrl.close_app()` explicitly; otherwise WinPVT stays in memory and interferes with
the next run.

### timeout_minutes sizing
For Standby Critical tests, a single full run can exceed 10 hours. Set `timeout_minutes` large
enough to cover the expected worst-case duration plus margin:
```json
"timeout_minutes": 800
```

### ExePath in Config.json is optional
If `ExePath` is absent or empty, the controller falls back to `WinPVTConfig.DEFAULT_CONFIG['exe_path']`.
Use:
```python
exe_path=winpvt_cfg.get('ExePath') or WinPVTConfig.DEFAULT_CONFIG['exe_path']
```

---

## Real-world Test Cases

| Test Case | Pattern | timeout_minutes | PvtFile |
|-----------|---------|----------------|---------|
| `stc1067_winpvt_standby_critical` | Two-phase startup + run | 800 | `Config/winpvt_prod.pvt` |
