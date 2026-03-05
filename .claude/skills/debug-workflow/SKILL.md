````skill
---
name: debug-workflow
description: Systematic debug process for ssd-testkit failures — test failures, tool crashes, UI automation errors, reboot-state bugs, and build issues. Use when user reports a bug, test failure, unexpected behaviour, or mentions debug / 排查 / 錯誤 / crash / hang.
---

# Debug Workflow — ssd-testkit

## Step 1 — Reproduce the Failure

Before changing anything, confirm you can reproduce:

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Re-run the failing test with full output
pytest <path/to/test_file.py>::<TestClass>::<test_method> -v -s --tb=long
```

For standalone scripts:
```powershell
python tests/verification/<script>.py
```

**Note:** hardware/integration tests require **Administrator** terminal.

---

## Step 2 — Check Logs First

Always read logs before guessing:

| Log file | Contents |
|----------|----------|
| `log/log.txt` | Runtime application logs (INFO+) |
| `log/log.err` | Runtime errors and tracebacks |
| `testlog/` | pytest captured output per test run |
| `packaging/log/log.txt` | Build pipeline output |

```powershell
# Tail last 100 lines of error log
Get-Content log\log.err -Tail 100
Get-Content log\log.txt -Tail 200
```

---

## Step 3 — Identify Which Layer Failed

```
test file  →  controller  →  process_manager / ui_monitor  →  external tool
```

| Symptom | Likely layer |
|---------|-------------|
| `ImportError` / `AttributeError` | Wrong module or config key — check `__init__.py` exports |
| `TimeoutError` / `MyToolTimeoutError` | `process_manager` or `ui_monitor` — tool didn't start/finish in time |
| `FileNotFoundError` for `.exe` | Binary not in `bin/` or path wrong in config |
| UI element not found (`pywinauto`) | Window title changed or tool version mismatch |
| Playwright selector failure | PHM web UI layout changed — dump `page.content()` to `tmp/` |
| Reboot test resumes at wrong step | `reboot_manager.py` state JSON corrupted — delete `testlog/*.json` |
| pytest `FAILED` with assertion | Check test fixture data and config JSON values |

---

## Step 4 — Isolate the Module

Run the smallest possible code path:

```python
# Quick controller smoke test (run in python REPL or tmp/ script)
from lib.testtool.<toolname>.controller import <ToolName>Controller
ctrl = <ToolName>Controller({"timeout": 30})
ctrl.start()
ctrl.join(timeout=35)
print(ctrl.result)
```

For UI tools, add `headless=False` to see what the automation is doing.

For process issues:
```powershell
# Check if the external tool process is running
Get-Process bit64, smismartcheck, phm -ErrorAction SilentlyContinue
# Kill stuck processes
Stop-Process -Name bit64 -Force
```

---

## Step 5 — Add Debug Logging

Temporarily increase log verbosity:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or in the controller, confirm `logger.debug()` calls are present.  
Check `lib/logger.py` for log level configuration.

---

## Step 6 — Run Unit Tests for the Affected Module

```powershell
pytest tests/unit/lib/<toolname>/ -v -s
```

If unit tests pass but integration fails → environment / hardware issue.  
If unit tests also fail → code regression.

---

## Step 7 — Common Fixes Checklist

- [ ] Binary exists at path specified in config JSON
- [ ] Running as **Administrator** (for hardware/registry tests)
- [ ] `requirements.txt` packages installed (`pip install -r requirements.txt`)
- [ ] No leftover state JSON from a previous failed reboot test (`testlog/*.json`)
- [ ] PHM web UI accessible at `http://localhost:1337` before PHM tests
- [ ] No orphan processes from previous run (`Get-Process bit64 | Stop-Process`)
- [ ] Config JSON keys match `DEFAULT_CONFIG` in `config.py`
- [ ] Windows Defender / AV not blocking test binary execution

---

## Step 8 — Minimal Reproducer for Bug Reports

Before filing / asking for help, create a minimal script in `tmp/`:

```python
# tmp/debug_<issue>.py
# Minimal repro — describe what this tests and what goes wrong
from lib.testtool.<toolname>.controller import ...
...
```

Run it and capture full output:
```powershell
python tmp\debug_<issue>.py 2>&1 | Tee-Object tmp\debug_out.txt
```
````
