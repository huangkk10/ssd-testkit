# SmartCheck Tool Reference

**Package location**: `lib/testtool/smartcheck/`
**Chocolatey package**: `bin/chocolatey/packages/smiwintools/`
**Install path**: `C:\tools\SmiWinTools`
**Key binary**: `C:\tools\SmiWinTools\SmartCheck.bat`

---

## Overview

SmartCheck is an SMI (Silicon Motion) CLI tool that runs SMART health checks on SSDs.
It is controlled via `SmartCheckController` (a `threading.Thread` subclass) which:

1. Launches `SmartCheck.bat` as a subprocess
2. Monitors `RunCard.ini` written by SmartCheck.bat for PASS/FAIL/ONGOING status
3. Exits immediately when RunCard.ini shows PASS or FAIL

---

## Package Structure

```
lib/testtool/smartcheck/
├── __init__.py              # exports SmartCheckController
├── controller.py            # main controller (threading.Thread subclass)
├── package_meta.yaml        # id=smiwintools, installs to C:\tools\SmiWinTools
└── exceptions.py            # SmartCheckError, SmartCheckConfigError, etc.
```

---

## Controller API

```python
from lib.testtool.smartcheck import SmartCheckController

ctrl = SmartCheckController(
    output_dir='./testlog/SmartCheckLog',  # where RunCard.ini and logs are written
)
ctrl.set_config(
    total_time=3,          # minutes SmartCheck.bat runs its own check cycle
    check_interval=3,      # seconds between RunCard.ini polls
    timeout=10,            # controller outer deadline in minutes
)
ctrl.start()               # launch thread (and SmartCheck.bat)
ctrl.join(timeout=630)     # wait up to timeout+30s
ctrl.stop()                # signal stop + kill SmartCheck.bat (if still running)

# Status values:
# None  — still running
# True  — PASS (no SMART errors)
# False — FAIL (SMART errors detected or timed out)
print(ctrl.status)
```

### `from_config_dict` factory (concurrent pattern)

```python
ctrl = SmartCheckController.from_config_dict(config.get('smartcheck', {}))
```

Used in the stc1685 concurrent BurnIN+SmartCheck pattern.

---

## SmartCheck.bat Path Resolution

`SmartCheckController` auto-resolves `SmartCheck.bat` via (in order):

1. `SMIWINTOOLS_PATH` env var → `{SMIWINTOOLS_PATH}/SmartCheck.bat`
2. `SSD_TESTKIT_ROOT` env var → `{SSD_TESTKIT_ROOT}/bin/SmiWinTools/SmartCheck.bat`
3. Legacy relative path → `./bin/SmiWinTools/SmartCheck.bat`

**No need to set `bat_path` in Config.json** — the env var approach is preferred.

---

## Tool Installation (tools.yaml)

```yaml
- id: smiwintools
  reinstall: false
  phase: pre_runcard    # inject env before any test step runs
  env:
    SMIWINTOOLS_PATH: "C:\\tools\\SmiWinTools"
```

> **Why explicit `env`?** `ToolInstaller._inject_env_from_meta('smiwintools')` looks for
> `lib/testtool/smiwintools/package_meta.yaml` but the meta lives at
> `lib/testtool/smartcheck/package_meta.yaml` → env is NOT auto-injected.
> Adding `env.SMIWINTOOLS_PATH` explicitly is the reliable workaround.

---

## Config.json Sections

### Standalone pre-check (quick health gate, ~3–10 min total)

```json
"smartcheck": {
  "output_dir": "./testlog/SmartCheckLog",
  "total_time": 3,
  "check_interval": 3,
  "timeout": 10
}
```

### Concurrent with BurnIN (long-running, 7 days)

```json
"smartcheck": {
  "output_dir": "./testlog/SmartLog",
  "total_time": 10080,
  "check_interval": 3,
  "timeout": 120
}
```

| Field | Unit | Notes |
|-------|------|-------|
| `total_time` | minutes | How long SmartCheck.bat itself runs; use 3 for quick pre-check |
| `check_interval` | seconds | RunCard.ini poll interval |
| `timeout` | minutes | Controller outer deadline; must be > `total_time` + startup overhead (≈4 min to find RunCard.ini) |

---

## Known Behaviour / Pitfalls

### RunCard.ini startup delay (~4 minutes)
SmartCheck.bat creates RunCard.ini only after its first cycle completes. The controller
logs `"RunCard.ini not found yet, waiting..."` for about 255 seconds (4+ min) before the
file appears. Set `timeout` ≥ `total_time` + 5 minutes.

### PASS vs PASSED (fixed 2026-04-21)
SmartCheck.bat writes `PASS` (not `PASSED`) to RunCard.ini.
Before the fix, `controller.py` compared `test_result == 'PASSED'` → never matched →
controller ran until full `timeout`. Now the comparison is `test_result in ('PASS', 'PASSED')`.

### status = None after timeout
If `ctrl.join()` returns and `ctrl.is_alive()` is False but `ctrl.status is None`,
the controller exited via timeout (status was never set to True). Treat as FAIL.

---

## Usage Patterns

### Pattern 1: Standalone Pre-Check

Use before another tool runs to gate on SSD health. See full example in:
`.claude/skills/scaffold-testcase/references/stc1685_example.md` → "Standalone SmartCheck Pre-Check Pattern"

### Pattern 2: Concurrent with BurnIN

Run SmartCheck in parallel with BurnIN for continuous SMART monitoring during stress test.
See full example in:
`.claude/skills/scaffold-testcase/references/stc1685_example.md` → "test_05 — Concurrent BurnIN + SmartCheck"

---

## Real-world Test Cases

| Test Case | Pattern | total_time | timeout |
|-----------|---------|-----------|---------|
| `stc1685_burnin` | Concurrent with BurnIN | 10080 min (7 days) | 120 min |
| `stc1067_winpvt_standby_critical` | Standalone pre-check | 3 min | 10 min |
