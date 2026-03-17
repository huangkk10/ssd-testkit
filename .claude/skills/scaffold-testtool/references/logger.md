# Logger Reference — `lib/logger.py`

> **Source file**: `lib/logger.py`  
> **Log format**: Log4j-style (date + level + short module + func:line)  
> **Updated**: 2026-03-17

---

## 1. Import

```python
from lib.logger import get_module_logger           # always required in every module
from lib.logger import log_phase                   # phase transition banner
from lib.logger import log_step_begin, log_step_end  # manual step banners (rarely needed)
from lib.logger import log_kv, log_table           # structured metric output
from lib.logger import log_exception               # exception + context + traceback
from lib.logger import clear_log_files             # reset log files (test precondition)
```

Use `get_module_logger(__name__)` at module level — never instantiate `logging.Logger` directly.

---

## 2. Log Output Format

**Format string (Log4j-style)**:
```
YYYY-MM-DD HH:MM:SS.mmm LEVEL  module         funcName            :line - message
```

**Column widths**:
- `LEVEL` — 5 chars fixed (`INFO `, `WARN `, `ERROR`, `DEBUG`)
- `module` — 14 chars, only the last two dotted segments (e.g. `phm.ctrl` not `lib.testtool.phm.controller`)
- `funcName` — 20 chars
- `lineno` — 3 chars right-aligned

**Example output**:
```
2026-03-17 10:23:01.456 INFO  test_main      test_01_precondition : 45 - [TEST_01] Precondition setup started
2026-03-17 10:23:55.001 WARN  phm.ctrl       terminate            :123 - [TEST_05] PHM terminate error (non-fatal)
2026-03-18 00:03:22.789 INFO  test_main      test_05_run_modern   :310 - PHM collector completed
2026-03-18 00:15:44.001 ERROR phm.ctrl       install              : 87 - PHM install failed: FileNotFoundError
```

**Key design decisions**:
- Date always included — safe for tests that run past midnight (cross-day)
- `funcName:line` allows immediate source location without reading a Python traceback
- module is truncated to last two segments to eliminate noise from long `lib.testtool.X.Y` paths

---

## 3. Log Files

| File | Level filter | Description |
|------|-------------|-------------|
| `./log/app.log` | INFO+ | Full run log (previously `log.txt`) |
| `./log/error.log` | ERROR+ | Errors only (previously `log.err`) |

Both files are created relative to the **current working directory** at the time the logger is first initialised. In integration tests, `_setup_working_directory(__file__)` sets this via `os.chdir()` before the logger is touched.

Both files start with a session banner on each new run:
```
================================================================================
  SESSION START: 2026-03-17 10:22:58
================================================================================
```

The banner is written automatically by `Logger.init_logging()` when a new `FileHandler` is created. It delineates separate runs in append-mode log files.

### Clearing log files (test precondition step)

```python
from lib.logger import clear_log_files

# In test_01_precondition — remove logs from previous runs before starting fresh
clear_log_files()
```

`clear_log_files()` closes the existing `FileHandler`s, deletes (or truncates) `app.log` and `error.log`, then re-initialises the logger so subsequent calls work normally.

---

## 4. VS Code Extension Colours

The project ships `.vscode/settings.json` with `Log File Highlighter` (`emilast.LogFileHighlighter`) patterns tuned for this format:

| Colour | Pattern matched |
|--------|----------------|
| Red (bold) | `\bERROR\b` |
| Orange (bold) | `\bWARN\b` |
| Blue | `\bINFO\b` |
| Grey | `\bDEBUG\b` |
| Grey (dim) | `funcName : line -` column |
| Purple (bold) | `[STEP N/N]` |
| Green (bold) | `PASS` |
| Red | `FAIL` |
| Yellow (bold) | `PRE-REBOOT`, `POST-REBOOT` |
| White on dark bg | `SESSION START` |

`.vscode/settings.json` also associates `*.err` with the `log` language so `error.log` gets the same highlighting.

---

## 5. Helper Functions

All helpers accept `lgr: logging.Logger` as their first argument — pass the module-level logger.

---

### `log_phase(lgr, phase_name)` — Phase transition banner

**When to use**: In `setup_test_class` to mark PRE-REBOOT / POST-REBOOT boundary.

```python
from lib.logger import log_phase

phase = "POST-REBOOT (recovering)" if cls.reboot_mgr.is_recovering() else "PRE-REBOOT"
log_phase(logger, phase)
```

**Output**:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Phase: PRE-REBOOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### `log_step_begin` / `log_step_end` — Step banners

**When to use**: Rarely — the `@step` decorator calls these automatically. Only use manually if you need a banner outside a decorated test method.

```python
from lib.logger import log_step_begin, log_step_end
import time

start = time.time()
log_step_begin(logger, step_no=1, desc="Initialize system", total=9)
# ... work ...
log_step_end(logger, step_no=1, passed=True, elapsed=time.time() - start, total=9)
```

**Output**:
```
────────────────────────────────────────────────────────────
  [STEP 1/9] Initialize system
────────────────────────────────────────────────────────────
  [STEP 1/9] PASS  |  Elapsed: 3.2s
────────────────────────────────────────────────────────────
```

---

### `log_kv(lgr, label, value, unit='')` — Key-value metric

**When to use**: Logging a single measured value (threshold check result, config value, etc.)

```python
from lib.logger import log_kv

log_kv(logger, "SW DRIPS", 85.3, "%")
log_kv(logger, "HW DRIPS", 91.2, "%")
log_kv(logger, "L1.2 Residency", 94.5, "%")
```

**Output**:
```
  SW DRIPS                       = 85.3 %
  HW DRIPS                       = 91.2 %
  L1.2 Residency                 = 94.5 %
```

---

### `log_table(lgr, headers, rows)` — ASCII table

**When to use**: Logging multiple sessions / devices / rows of metric data in one block.

```python
from lib.logger import log_table

log_table(logger,
    ["Session", "SW DRIPS", "HW DRIPS"],
    [[s.session_id,
      f"{s.sw_pct}%" if s.sw_pct is not None else "N/A",
      f"{s.hw_pct}%" if s.hw_pct is not None else "N/A"]
     for s in sessions]
)
```

**Output**:
```
┌─────────┬──────────┬──────────┐
│ Session │ SW DRIPS │ HW DRIPS │
├─────────┼──────────┼──────────┤
│ 1       │ 85.3%    │ 91.2%    │
│ 2       │ 78.1%    │ 82.0%    │
└─────────┴──────────┴──────────┘
```

---

### `log_exception(lgr, msg, exc, context=None)` — Exception with context

**When to use**: Inside `except` blocks — captures the active traceback plus optional context dict.

```python
from lib.logger import log_exception

try:
    ctrl.install()
except Exception as e:
    log_exception(logger, "PHM install failed", e,
                  context={"install_path": cfg["install_path"], "step": "TEST_02"})
    raise
```

**Output in `error.log`**:
```
2026-03-18 00:15:44.001 ERROR phm.ctrl       install              : 87 - PHM install failed: FileNotFoundError: [WinError 2] ...
  Context [install_path] = C:\PHM
  Context [step] = TEST_02
  Traceback (most recent call last):
    File "lib/testtool/phm/controller.py", line 87, in install
      ...
```

> **Note**: `log_exception` must be called from inside an `except` block — `traceback.format_exc()` only captures the active exception.

---

## 6. `@step` Decorator

```python
from framework.decorators import step
```

The decorator **automatically** calls `log_step_begin` and `log_step_end` around every decorated test method — no manual banner needed:

```python
@pytest.mark.order(1)
@step(1, "Precondition — cleanup and create log directories")
def test_01_precondition(self):
    logger.info("[TEST_01] Starting precondition")
    # ... work ...
    # banner + PASS/FAIL + Elapsed are emitted automatically
```

**What the decorator does**:
1. Calls `log_step_begin(lgr, step_number, description)` before the method body
2. Runs the method
3. Calls `log_step_end(lgr, step_number, passed=True/False, elapsed=Xs)` after
4. Re-raises any exception so pytest still sees the failure

The logger inside the decorator is `logging.getLogger(func.__module__)` — it uses the module where the test method is defined, so the `module` column in the log will correctly show `test_main`.

---

## 7. Standard Module Pattern

Every `lib/testtool/<pkg>/` module should follow this pattern:

```python
from lib.logger import get_module_logger

logger = get_module_logger(__name__)


class MyController:
    def run(self):
        logger.info("Starting run")
        try:
            self._do_work()
        except Exception as exc:
            from lib.logger import log_exception
            log_exception(logger, "Run failed", exc,
                          context={"config": self._config})
            raise
```

- Import `log_exception` lazily inside the `except` block (avoids circular import risk)
- Use `logger.warning(...)` for non-fatal issues that callers should know about
- Use `logger.debug(...)` for verbose internal state (hidden at INFO level)
