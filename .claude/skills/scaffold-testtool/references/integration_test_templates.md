# Integration Test Templates Reference

Integration tests live under `tests/integration/lib/testtool/test_<package_name>/`.  
Ground truth: `tests/integration/lib/testtool/test_cdi/` (CDI), `test_burnin/` (BurnIN).

**Key difference from unit tests:** Integration tests run the **real executable** — nothing is mocked.

---

## Directory Structure

```
tests/integration/lib/testtool/test_<package_name>/
├── __init__.py
├── conftest.py               # tool env fixture + marker registration
└── test_<package_name>_workflow.py   # actual integration tests
```

---

## `Config.json` — Shared Tool Configuration

**Location:** `tests/integration/Config/Config.json`

Every tool gets its own top-level key. Add a new section when scaffolding a new library:

```json
{
  "<package_name>": {
    "ExePath":      "./bin/<ToolDir>/<executable>",
    "LogPath":      "./testlog/<ToolName>Log",
    "LogPrefix":    "",
    "timeout":      120
  }
}
```

**Real examples already in Config.json:**
```json
"burnin": {
  "installer":             "./bin/BurnIn/bitwindows.exe",
  "install_path":          "C:\\Program Files\\BurnInTest",
  "test_duration_minutes": 1,
  "test_drive_letter":     "D"
},
"smartcheck": {
  "bat_path":   "./bin/SmiWinTools/SmartCheck.bat",
  "output_dir": "./testlog/SmartLog",
  "total_time": 10080
},
"cdi": {
  "ExePath":                "./bin/CrystalDiskInfo/DiskInfo64.exe",
  "LogPath":                "./testlog/CDILog",
  "ScreenShotDriveLetter":  "C:"
}
```

**How to read Config.json in a test fixture:**

```python
# tests/integration/conftest.py already provides TestCaseConfiguration
# which exposes tool_config — a lazy-loaded parsed JSON dict.

@pytest.fixture(scope="session")
def testcase_config(test_root):
    from conftest import TestCaseConfiguration
    return TestCaseConfiguration(test_root / "integration" / "client_pcie_...")

# Then in your test:
def test_something(testcase_config):
    tool_cfg = testcase_config.tool_config["<package_name>"]
    exe = tool_cfg["ExePath"]
```

---

## `conftest.py` Template

```python
"""
<Tool> Integration Test Fixtures and Configuration

Provides pytest fixtures for <Tool> integration tests.
Requirements:
  - <executable> present at the configured path
  - Real Windows environment
  - Run as Administrator (if the tool requires raw hardware access)

Environment-variable overrides
-------------------------------
<TOOL>_EXE_PATH    path to <executable>
<TOOL>_LOG_DIR     output directory for this test session
<TOOL>_TIMEOUT     per-test timeout in seconds (default 120)
"""

import os
import time
import pytest
from pathlib import Path
from typing import Dict, Any


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real environment)"
    )
    config.addinivalue_line(
        "markers", "requires_<package_name>: mark test as requiring <executable>"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


@pytest.fixture(scope="session")
def test_root() -> Path:
    """Return the workspace root (ssd-testkit/)."""
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="session")
def <package_name>_env(test_root) -> Dict[str, Any]:
    """
    Provide <Tool> test environment configuration.

    Tool binary search order:
      1. Environment variable <TOOL>_EXE_PATH
      2. tests/unit/lib/testtool/bin/<ToolDir>/<executable>  (shared test binaries)
      3. Config.json path (if TestCaseConfiguration is available)

    +-----------------------+--------------------------------------------------+
    | Env var               | Default                                          |
    +-----------------------+--------------------------------------------------+
    | <TOOL>_EXE_PATH       | tests/unit/lib/testtool/bin/<ToolDir>/<exe>      |
    | <TOOL>_LOG_DIR        | tests/testlog/<package_name>_integration_<ts>    |
    | <TOOL>_TIMEOUT        | 120                                              |
    +-----------------------+--------------------------------------------------+
    """
    bin_path = test_root / "tests" / "unit" / "lib" / "testtool" / "bin" / "<ToolDir>"
    default_exe = str(bin_path / "<executable>")

    timestamp = int(time.time())
    testlog_dir = test_root / "tests" / "testlog"
    testlog_dir.mkdir(parents=True, exist_ok=True)
    default_log_dir = str(testlog_dir / f"<package_name>_integration_{timestamp}")

    return {
        'executable_path': os.getenv("<TOOL>_EXE_PATH", default_exe),
        'log_dir':         os.getenv("<TOOL>_LOG_DIR",  default_log_dir),
        'timeout':         int(os.getenv("<TOOL>_TIMEOUT", "120")),
        # Add tool-specific params here
    }


@pytest.fixture(scope="session")
def check_environment(<package_name>_env):
    """Skip the entire session if the executable is not present."""
    exe = Path(<package_name>_env['executable_path'])
    if not exe.exists():
        pytest.skip(
            f"<executable> not found at '{exe}'. "
            f"Set <TOOL>_EXE_PATH to the correct location."
        )
    return <package_name>_env


@pytest.fixture(scope="session")
def log_dir(<package_name>_env) -> Path:
    """Create and return the session-scoped log directory."""
    path = Path(<package_name>_env['log_dir'])
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def clean_log_dir(log_dir) -> Path:
    """
    Per-test sub-directory so output files do not bleed across tests.
    NOT deleted after the test — files remain for post-test inspection.
    """
    sub = log_dir / f"run_{int(time.time() * 1000)}"
    sub.mkdir(parents=True, exist_ok=True)
    yield sub
```

---

## `test_<package_name>_workflow.py` Template

```python
"""
<Tool> Controller Integration Tests

These tests run against a REAL <executable> on a real Windows machine.
Nothing is mocked.

Requirements
------------
- <executable> present (set <TOOL>_EXE_PATH or use default path)
- Real Windows environment

Environment-variable overrides
-------------------------------
<TOOL>_EXE_PATH       path to <executable>
<TOOL>_LOG_DIR        base directory for output files
<TOOL>_TIMEOUT        per-test timeout in seconds (default 120)

Run only integration tests
--------------------------
    pytest tests/integration/lib/testtool/test_<package_name>/ -v -m "integration"

Skip integration tests
----------------------
    pytest ... -m "not integration"
"""

import sys
from pathlib import Path
import pytest

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.testtool.<package_name> import <Tool>Controller
from lib.testtool.<package_name>.exceptions import <Tool>Error


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_controller(<package_name>_env, log_dir, **extra) -> <Tool>Controller:
    """Build a controller pointed at the given log directory."""
    return <Tool>Controller(
        executable_path=<package_name>_env['executable_path'],
        log_path=str(log_dir),
        timeout_seconds=<package_name>_env['timeout'],
        **extra,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_<package_name>
@pytest.mark.slow
class Test<Tool>ControllerIntegration:
    """End-to-end <Tool> controller tests against real <executable>."""

    @pytest.mark.timeout(180)
    def test_full_workflow(self, <package_name>_env, check_environment, clean_log_dir):
        """
        T01 — Run complete workflow: start → wait → check result.
        """
        ctrl = _make_controller(<package_name>_env, clean_log_dir)
        ctrl.start()
        ctrl.join(timeout=<package_name>_env['timeout'])

        assert ctrl.status is True, f"<Tool> returned status={ctrl.status}"

    @pytest.mark.timeout(30)
    def test_stop_signal(self, <package_name>_env, check_environment, clean_log_dir):
        """
        T02 — Verify stop() terminates the controller cleanly.
        """
        import threading
        ctrl = _make_controller(<package_name>_env, clean_log_dir)
        ctrl.start()
        threading.Timer(3.0, ctrl.stop).start()
        ctrl.join(timeout=15)
        # status is False (stopped early) — that is acceptable here
        assert ctrl.status is not None, "status should be set after stop()"
```

---

## Rules Summary

| Rule | Detail |
|------|--------|
| **Location** | `tests/integration/lib/testtool/test_<package_name>/` |
| **Config.json** | Add a `"<package_name>"` section to `tests/integration/Config/Config.json` |
| **Executable path** | Support env-var override (`<TOOL>_EXE_PATH`); default to `tests/unit/lib/testtool/bin/<ToolDir>/` |
| **`check_environment`** | Use `pytest.skip()` if exe not found — never let the test fail due to missing binary |
| **Markers** | Always add `@pytest.mark.integration` + `@pytest.mark.requires_<package_name>` |
| **No mocks** | Integration tests run real executables; mocking belongs in unit tests |
| **`clean_log_dir`** | Each test gets its own timestamped sub-dir under `log_dir` |
| **`scope="session"`** | `<package_name>_env`, `check_environment`, `log_dir` are session-scoped |
| **Scope** | `clean_log_dir` is function-scoped (fresh dir per test) |
| **Run command** | `pytest tests/integration/lib/testtool/test_<package_name>/ -v -m "integration"` |
| **Skip command** | Add `-m "not integration"` to any pytest run to exclude all integration tests |
