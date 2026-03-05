````skill
---
name: repo-understanding
description: Complete reference for the ssd-testkit repository — architecture, folder purposes, coding conventions, dependency rules, and build pipeline. Use this skill whenever you need to understand what a folder/file does, what coding pattern to follow, or how the project fits together. 當 user 問「這個 repo 是什麼」、「這個 folder 幹嘛」、「怎麼寫新程式」時請先查此 skill。
---

# SSD-TestKit — Repository Understanding

## Project Purpose

`ssd-testkit` is a **Windows-only** SSD validation automation framework.  
It wraps third-party test tools (BurnIN, CrystalDiskInfo, PHM, PwrTest, SmartCheck, OsReboot, OsConfig…) into Python packages and orchestrates them via `pytest` to produce a single-EXE deliverable for field engineers.

---

## Top-Level Folder Map

```
ssd-testkit/
├── framework/          # Core test-runner machinery (reboot, decorators, utils)
├── lib/                # Reusable libraries
│   ├── logger.py       # Project-wide structured logger
│   └── testtool/       # One sub-package per wrapped tool  ← MAIN GROWTH AREA
├── tests/              # pytest test cases
│   ├── integration/    # Real-hardware / end-to-end tests
│   ├── unit/           # Fast, mocked unit tests
│   └── verification/   # Smoke / sanity scripts (not pytest suites)
├── packaging/          # PyInstaller build pipeline → RunTest.exe
├── tools/              # One-off developer utilities (not shipped)
├── tmp/                # Scratch / debug files (gitignored)
└── .claude/skills/     # Claude agent skills (this file lives here)
```

---

## `framework/` — Core Machinery

| File | Purpose |
|------|---------|
| `base_test.py` | `BaseTest` — all integration test classes inherit this; handles reboot state persistence |
| `decorators.py` | `@test_step` — wraps a method as a named, logged test step |
| `reboot_manager.py` | JSON-persisted state machine for cross-reboot test resumption |
| `system_time_manager.py` | Freeze / restore system clock during tests |
| `concurrent_runner.py` | `ConcurrentRunner` — run multiple callables in parallel with timeout |
| `test_utils.py` | Shared helpers (retry, wait_for, etc.) |

**Rule**: Framework code must NOT import from `lib/testtool/`. That direction is always `tests → lib → framework`.

---

## `lib/testtool/` — Tool Sub-Packages

Every tool lives in its own sub-package following the `burnin/` template:

```
lib/testtool/<toolname>/
├── __init__.py          # exports + usage docstring
├── config.py            # DEFAULT_CONFIG dict + merge_config()
├── controller.py        # Main controller (threading.Thread subclass)
├── exceptions.py        # Exception hierarchy
├── process_manager.py   # Install / start / stop / kill  [if needed]
├── script_generator.py  # .bits / .ini / script generation [if needed]
├── ui_monitor.py        # pywinauto / Playwright UI automation [if needed]
└── log_parser.py        # Structured log / report parser [if needed]
```

**Known tool packages:**

| Package | Tool | Notes |
|---------|------|-------|
| `burnin/` | BurnIN (bit64.exe) | GUI, script generator, pywinauto monitor |
| `cdi/` | CrystalDiskInfo | CLI, log parser |
| `phm/` | PHM collector | Playwright web UI at localhost:1337 |
| `pwrtest/` | PwrTest | CLI, log parser |
| `smartcheck/` | SmiSmartCheck | CLI |
| `reboot/` | OsReboot | BAT/CLI, state manager |
| `osconfig/` | OsConfig | Registry + actions + state manager |
| `sleepstudy/` | SleepStudy | CLI, HTML log parser |
| `python_installer/` | Python installer helper | process manager only |

Legacy single-file wrappers (`BurnIN.py`, `CDI.py`, etc. at the `testtool/` root) are **deprecated** — do not add new code to them; use the sub-package instead.

---

## `tests/` Layout

```
tests/
├── integration/<customer>_<platform>/   # One folder per test scenario/STC
│   ├── conftest.py                      # Fixtures for that scenario
│   ├── Config/                          # JSON configs consumed by test
│   ├── bin/                             # Bundled binaries
│   └── test_*.py                        # pytest test modules
├── unit/lib/                            # Unit tests mirroring lib/ structure
└── verification/                        # Manual smoke scripts (run standalone)
```

**pytest markers** (defined in `pytest.ini`):
- `slow`, `integration`, `unit`, `admin`, `hardware`, `real`, `real_bat`
- Customer tags: `client_lenovo`, etc.

---

## `packaging/` — Build Pipeline

```
packaging/
├── build_config.yaml   # What to bundle (test IDs, bin paths, config files)
├── build.py            # PyInstaller orchestrator
├── build.bat           # One-click Windows build script
├── run_test.py         # EXE entry point
└── run_test.spec       # PyInstaller spec (committed to git)
```

**Build output**: `packaging/release/<tag>/RunTest.exe` — a single self-extracting EXE that includes Python, all dependencies, binaries, and test configs.

---

## Coding Standards

### Python style
- Python 3.10+ (type hints encouraged, not mandatory)
- `snake_case` for modules/functions/variables; `PascalCase` for classes
- Max line length: 120 characters
- Imports order: stdlib → third-party → local (framework → lib)
- No bare `except:`; catch specific exceptions from `exceptions.py`

### Logging
```python
from lib.logger import get_logger
logger = get_logger(__name__)
logger.info("message")   # INFO for milestones
logger.debug("message")  # DEBUG for internals
```
Never use `print()` in library code.

### Config pattern
```python
DEFAULT_CONFIG = {
    "timeout": 300,
    "retry": 3,
}

def merge_config(user_config: dict) -> dict:
    config = DEFAULT_CONFIG.copy()
    config.update(user_config or {})
    return config
```

### Controller pattern
```python
class MyToolController(threading.Thread):
    def __init__(self, config: dict | None = None):
        super().__init__(daemon=True)
        self.config = merge_config(config)
        self.result = None
        self._stop_event = threading.Event()

    def run(self):
        ...

    def stop(self):
        self._stop_event.set()
```

### Exception hierarchy
```python
class MyToolError(Exception): ...
class MyToolTimeoutError(MyToolError): ...
class MyToolNotFoundError(MyToolError): ...
```

---

## Dependency Rules (import direction)

```
tests/  →  lib/testtool/  →  lib/logger.py
tests/  →  framework/
framework/  →  lib/logger.py
```

- `framework/` must NOT import from `lib/testtool/`
- `lib/testtool/<a>/` must NOT import from `lib/testtool/<b>/` (no cross-tool deps)
- All third-party imports must be in `requirements.txt`

---

## OS / Environment Constraints

- **Windows only** — all paths use `\\` or `pathlib.Path`
- Tests that touch hardware require **Administrator** privileges (`@pytest.mark.admin`)
- External binaries live in `tests/integration/<scenario>/bin/` and are **not** committed to git (downloaded or copied before test)
- The bundled EXE runs on the **DUT** (Device Under Test) machine, not a remote CI server

---

## Key Config Files

| File | Purpose |
|------|---------|
| `pytest.ini` | Test discovery, markers, output options |
| `requirements.txt` | pip dependencies |
| `packaging/build_config.yaml` | Which tests/bins to bundle into the EXE |
| `.gitignore` | Excludes `packaging/build/`, `packaging/dist/`, `testlog/`, `.venv/` |
````
