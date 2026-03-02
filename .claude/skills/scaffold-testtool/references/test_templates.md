# Unit Test Templates Reference

Unit tests for each testtool library live under `tests/unit/lib/testtool/test_<package_name>/`.  
Ground truth: `tests/unit/lib/testtool/test_burnin/`

---

## Directory Structure

```
tests/unit/lib/testtool/test_<package_name>/
├── __init__.py
├── conftest.py          # shared fixtures
├── test_exceptions.py   # exception hierarchy tests
├── test_config.py       # config class tests
└── test_controller.py   # controller tests (mocked dependencies)
```

Optional (only if the module exists):
```
├── test_process_manager.py   # if process_manager.py exists
├── test_script_generator.py  # if script_generator.py exists
├── test_ui_monitor.py        # if ui_monitor.py exists
└── test_log_parser.py        # if log_parser.py exists
```

---

## `conftest.py` Template

```python
"""
Pytest configuration and fixtures for <Tool> unit tests.
"""

import pytest
import tempfile
import os


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_log_path(temp_dir):
    """Temporary log file path (not created yet)."""
    return os.path.join(temp_dir, 'test.log')


@pytest.fixture
def sample_config():
    """Minimal valid configuration dictionary."""
    return {
        'executable_path': './bin/tool.exe',
        'timeout_seconds': 60,
    }
```

Adapt `sample_config` to include the tool's required params from `DEFAULT_CONFIG`.

---

## `test_exceptions.py` Template

Uses **pytest** style (`class TestX` + `def test_...`).

```python
"""
Unit tests for <Tool> exceptions module.
"""

import pytest
from lib.testtool.<package_name>.exceptions import (
    <Tool>Error,
    <Tool>ConfigError,
    <Tool>TimeoutError,
    <Tool>ProcessError,
    <Tool>TestFailedError,
    # <Tool>InstallError,   # uncomment if requires_install
    # <Tool>UIError,        # uncomment if has_ui
)


class Test<Tool>Exceptions:
    """Test suite for <Tool> exception classes."""

    def test_base_exception(self):
        """Test <Tool>Error base exception."""
        with pytest.raises(<Tool>Error):
            raise <Tool>Error("Base error")
        try:
            raise <Tool>Error("Test message")
        except <Tool>Error as e:
            assert str(e) == "Test message"

    def test_config_error_raised(self):
        with pytest.raises(<Tool>ConfigError):
            raise <Tool>ConfigError("bad config")

    def test_config_error_inherits_base(self):
        with pytest.raises(<Tool>Error):
            raise <Tool>ConfigError("bad config")

    def test_timeout_error_raised(self):
        with pytest.raises(<Tool>TimeoutError):
            raise <Tool>TimeoutError("timed out")

    def test_timeout_error_inherits_base(self):
        with pytest.raises(<Tool>Error):
            raise <Tool>TimeoutError("timed out")

    def test_process_error_raised(self):
        with pytest.raises(<Tool>ProcessError):
            raise <Tool>ProcessError("process failed")

    def test_test_failed_error_raised(self):
        with pytest.raises(<Tool>TestFailedError):
            raise <Tool>TestFailedError("test failed")

    # --- Conditional: only if requires_install ---
    def test_install_error_raised(self):
        with pytest.raises(<Tool>InstallError):
            raise <Tool>InstallError("install failed")

    def test_install_error_inherits_base(self):
        with pytest.raises(<Tool>Error):
            raise <Tool>InstallError("install failed")
    # --- End conditional ---

    def test_exception_hierarchy(self):
        """All exceptions must inherit from <Tool>Error and Exception."""
        sub_classes = [
            <Tool>ConfigError,
            <Tool>TimeoutError,
            <Tool>ProcessError,
            <Tool>TestFailedError,
        ]
        for exc_class in sub_classes:
            assert issubclass(exc_class, <Tool>Error)
            assert issubclass(exc_class, Exception)

    def test_exception_with_message(self):
        """Exception message is preserved."""
        msg = "detailed error: param='x', value=-1, reason='must be >= 0'"
        try:
            raise <Tool>ConfigError(msg)
        except <Tool>ConfigError as e:
            assert "param='x'" in str(e)
            assert "-1" in str(e)
```

---

## `test_config.py` Template

Uses **pytest** style. `sample_config` fixture comes from `conftest.py`.

```python
"""
Unit tests for <Tool> configuration module.
"""

import pytest
from lib.testtool.<package_name>.config import <Tool>Config
from lib.testtool.<package_name>.exceptions import <Tool>ConfigError


class Test<Tool>Config:
    """Test suite for <Tool>Config class."""

    # ----- get_default_config -----

    def test_returns_dict(self):
        config = <Tool>Config.get_default_config()
        assert isinstance(config, dict)

    def test_required_keys_present(self):
        config = <Tool>Config.get_default_config()
        # List every key that MUST exist
        for key in ['executable_path', 'timeout_seconds', 'log_path']:
            assert key in config, f"Missing key: {key}"

    def test_returns_copy(self):
        """Modifying one copy must not affect another."""
        c1 = <Tool>Config.get_default_config()
        c2 = <Tool>Config.get_default_config()
        c1['timeout_seconds'] = 9999
        assert c2['timeout_seconds'] != 9999

    # ----- validate_config -----

    def test_validate_valid(self, sample_config):
        assert <Tool>Config.validate_config(sample_config) is True

    def test_validate_empty(self):
        assert <Tool>Config.validate_config({}) is True

    def test_validate_unknown_key(self):
        with pytest.raises(<Tool>ConfigError):
            <Tool>Config.validate_config({'nonexistent_key': 1})

    def test_validate_wrong_type(self):
        """timeout_seconds must be int, not str."""
        with pytest.raises(<Tool>ConfigError):
            <Tool>Config.validate_config({'timeout_seconds': "60"})

    # ----- merge_config -----

    def test_merge_applies_overrides(self):
        base = <Tool>Config.get_default_config()
        merged = <Tool>Config.merge_config(base, {'timeout_seconds': 999})
        assert merged['timeout_seconds'] == 999

    def test_merge_preserves_base(self):
        base = <Tool>Config.get_default_config()
        original_log = base['log_path']
        merged = <Tool>Config.merge_config(base, {'timeout_seconds': 999})
        assert merged['log_path'] == original_log

    def test_merge_rejects_invalid_overrides(self):
        base = <Tool>Config.get_default_config()
        with pytest.raises(<Tool>ConfigError):
            <Tool>Config.merge_config(base, {'bad_key': 'bad_value'})
```

---

## `test_controller.py` Template

Uses **pytest** style (`@pytest.fixture`, `@pytest.mark.parametrize`).  
All external dependencies (subprocess, file system, sub-components) must be **mocked**.

### ⚠️ Wait-loop mock pattern

If `controller.py` calls `subprocess.run(...)` (or `Popen`) and then enters a
`time.sleep` loop waiting for an external event (e.g. waiting for the OS to reboot),
**do NOT pre-set `_stop_event` before the thread starts.**  Pre-setting it causes
the controller to short-circuit before calling `subprocess.run`, so assertions like
`mock_subprocess.assert_called_once()` fail unexpectedly.

**Correct approach** — patch `time.sleep` to trigger the stop event on first call:

```python
@pytest.fixture
def fast_wait(ctrl):
    """
    Patch time.sleep so the post-subprocess wait loop exits immediately.
    subprocess.run and state saves still execute before the loop is entered.
    """
    def _sleep(_secs):
        ctrl._stop_event.set()   # fires on first sleep() call inside the loop

    with patch('lib.testtool.<package_name>.controller.time.sleep', side_effect=_sleep):
        yield ctrl
```

Use `fast_wait` (instead of `ctrl`) in any test that needs to verify that
`subprocess.run` was called:

```python
def test_issues_command(fast_wait, patch_subprocess):
    fast_wait.start()
    fast_wait.join(timeout=5)
    assert patch_subprocess.called
    assert patch_subprocess.call_args[0][0][0] == '<executable>'
```

Use `ctrl` (with `ctrl._stop_event.set()` called manually) only in tests that
verify the **pre-subprocess abort path** (stop fires before the command is issued):

```python
def test_stop_before_command(ctrl, patch_subprocess):
    ctrl._stop_event.set()   # stop fires before subprocess.run
    ctrl.start()
    ctrl.join(timeout=5)
    patch_subprocess.assert_not_called()
    assert ctrl.status is False
```

---

```python
"""
Unit tests for <Tool> Controller.
Tests <Tool>Controller with mocked dependencies.
"""

import threading
import pytest
from unittest.mock import patch

from lib.testtool.<package_name>.controller import <Tool>Controller
from lib.testtool.<package_name>.exceptions import (
    <Tool>ConfigError,
    <Tool>TimeoutError,
    <Tool>ProcessError,
)


# ── Minimal valid kwargs ────────────────────────────────────────────────────────────────────────────
_VALID_KWARGS = {
    'executable_path': './bin/tool.exe',
    'timeout_seconds': 60,
}


@pytest.fixture(autouse=True)
def patch_path_exists():
    """Prevent __init__ / _execute_test from checking real file paths."""
    with patch('pathlib.Path.exists', return_value=True):
        yield


@pytest.fixture
def ctrl():
    """Return a fresh, not-started controller."""
    return <Tool>Controller(**_VALID_KWARGS)


# ── Initialization ─────────────────────────────────────────────────────────────────────────────
class Test<Tool>ControllerInit:

    def test_sets_defaults(self, ctrl):
        assert ctrl._config['timeout_seconds'] == 60
        assert ctrl.status is None
        assert ctrl.error_count == 0

    def test_is_thread(self, ctrl):
        assert isinstance(ctrl, threading.Thread)

    def test_invalid_config_raises(self):
        with pytest.raises(<Tool>ConfigError):
            <Tool>Controller(unknown_param='bad')


# ── set_config ────────────────────────────────────────────────────────────────────────────────
class Test<Tool>ControllerSetConfig:

    def test_updates_value(self, ctrl):
        ctrl.set_config(timeout_seconds=120)
        assert ctrl._config['timeout_seconds'] == 120

    def test_invalid_key_raises(self, ctrl):
        with pytest.raises(<Tool>ConfigError):
            ctrl.set_config(bad_key='value')


# ── stop ─────────────────────────────────────────────────────────────────────────────────────
class Test<Tool>ControllerStop:

    def test_sets_stop_event(self, ctrl):
        assert not ctrl._stop_event.is_set()
        ctrl.stop()
        assert ctrl._stop_event.is_set()


# ── run (mocked execution) ───────────────────────────────────────────────────────────────
class Test<Tool>ControllerRun:

    def test_run_sets_true_on_success(self, ctrl):
        """run() sets status=True when _execute_test succeeds."""
        def fake_execute():
            ctrl._status = True
        with patch.object(<Tool>Controller, '_execute_test', side_effect=fake_execute):
            ctrl.start()
            ctrl.join(timeout=5)
        assert ctrl.status is True

    @pytest.mark.parametrize("exc_cls", [
        <Tool>TimeoutError,
        <Tool>ProcessError,
    ])
    def test_run_sets_false_on_exception(self, exc_cls):
        """run() sets status=False for every tool-specific exception."""
        with patch.object(<Tool>Controller, '_execute_test', side_effect=exc_cls("err")):
            c = <Tool>Controller(**_VALID_KWARGS)
            c.start()
            c.join(timeout=5)
        assert c.status is False
```

---

## `test_log_parser.py` Template *(only if `has_log_parser: true`)*

Use **pytest** class style (same as `test_exceptions.py` / `test_config.py`).
All tests use fixture HTML strings written to `temp_dir` — no hard-coded paths.

```python
"""
Unit tests for <Tool>LogParser and <Tool>TestResult.
Uses fixture report strings — no real executables or network access.
"""

import os
import pytest
from lib.testtool.<toolname>.log_parser import <Tool>LogParser, <Tool>TestResult
from lib.testtool.<toolname>.exceptions import <Tool>LogParseError


# ---------------------------------------------------------------------------
# Fixtures (can also live in conftest.py)
# ---------------------------------------------------------------------------

_PASS_HTML = """
<html><head><title><Tool> Test Report</title></head><body>
<h1>Test Results</h1>
<p>Test Result: PASS</p>
<p>Total Cycles: 10</p>
<p>Completed Cycles: 10</p>
<p>Start Time: 2026-01-01 10:00:00</p>
<p>End Time: 2026-01-01 11:00:00</p>
</body></html>
"""

_FAIL_HTML = """
<html><head><title><Tool> Test Report</title></head><body>
<h1>Test Results</h1>
<p>Test Result: FAIL</p>
<p>Total Cycles: 10</p>
<p>Completed Cycles: 7</p>
<p>Error: Disk read failure on sector 4096</p>
</body></html>
"""


@pytest.fixture
def html_pass_file(tmp_path):
    p = tmp_path / 'pass_report.html'
    p.write_text(_PASS_HTML, encoding='utf-8')
    return str(p)


@pytest.fixture
def html_fail_file(tmp_path):
    p = tmp_path / 'fail_report.html'
    p.write_text(_FAIL_HTML, encoding='utf-8')
    return str(p)


# ---------------------------------------------------------------------------
# <Tool>TestResult dataclass tests
# ---------------------------------------------------------------------------

class TestResult:
    def test_default_status_unknown(self):
        r = <Tool>TestResult()
        assert r.status == 'UNKNOWN'

    def test_default_errors_empty_list(self):
        r = <Tool>TestResult()
        assert r.errors == []

    def test_default_cycles_zero(self):
        r = <Tool>TestResult()
        assert r.total_cycles == 0
        assert r.completed_cycles == 0


# ---------------------------------------------------------------------------
# <Tool>LogParser — PASS report
# ---------------------------------------------------------------------------

class TestLogParserPass:
    def test_parse_status_pass(self, html_pass_file):
        result = <Tool>LogParser().parse_report(html_pass_file)
        assert result.status == 'PASS'

    def test_parse_pass_no_errors(self, html_pass_file):
        result = <Tool>LogParser().parse_report(html_pass_file)
        assert result.errors == []

    def test_parse_pass_cycles(self, html_pass_file):
        result = <Tool>LogParser().parse_report(html_pass_file)
        assert result.total_cycles == 10
        assert result.completed_cycles == 10

    def test_parse_pass_timestamps(self, html_pass_file):
        result = <Tool>LogParser().parse_report(html_pass_file)
        assert result.start_time is not None
        assert result.end_time is not None

    def test_parse_pass_raw_path_set(self, html_pass_file):
        result = <Tool>LogParser().parse_report(html_pass_file)
        assert result.raw_report_path != ''


# ---------------------------------------------------------------------------
# <Tool>LogParser — FAIL report
# ---------------------------------------------------------------------------

class TestLogParserFail:
    def test_parse_status_fail(self, html_fail_file):
        result = <Tool>LogParser().parse_report(html_fail_file)
        assert result.status == 'FAIL'

    def test_parse_fail_has_errors(self, html_fail_file):
        result = <Tool>LogParser().parse_report(html_fail_file)
        assert len(result.errors) > 0

    def test_parse_fail_partial_cycles(self, html_fail_file):
        result = <Tool>LogParser().parse_report(html_fail_file)
        assert result.completed_cycles < result.total_cycles


# ---------------------------------------------------------------------------
# <Tool>LogParser — error handling
# ---------------------------------------------------------------------------

class TestLogParserErrors:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(<Tool>LogParseError, match='not found'):
            <Tool>LogParser().parse_report(str(tmp_path / 'missing.html'))

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / 'empty.html'
        p.write_text('', encoding='utf-8')
        with pytest.raises(<Tool>LogParseError, match='empty'):
            <Tool>LogParser().parse_report(str(p))

    def test_unknown_status_no_pass_fail_keyword(self, tmp_path):
        p = tmp_path / 'unknown.html'
        p.write_text('<html><body>No verdict here</body></html>', encoding='utf-8')
        result = <Tool>LogParser().parse_report(str(p))
        assert result.status == 'UNKNOWN'


# ---------------------------------------------------------------------------
# parse_reports_batch
# ---------------------------------------------------------------------------

class TestLogParserBatch:
    def test_batch_missing_dir_raises(self, tmp_path):
        with pytest.raises(<Tool>LogParseError):
            <Tool>LogParser().parse_reports_batch(str(tmp_path / 'no_such_dir'))

    def test_batch_empty_dir_returns_empty_list(self, tmp_path):
        results = <Tool>LogParser().parse_reports_batch(str(tmp_path))
        assert results == []

    def test_batch_multiple_reports(self, tmp_path):
        for i in range(3):
            (tmp_path / f'report_{i}.html').write_text(_PASS_HTML, encoding='utf-8')
        results = <Tool>LogParser().parse_reports_batch(str(tmp_path))
        assert len(results) == 3


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

class TestLogParserSummarize:
    def test_summarize_counts(self):
        results = [
            <Tool>TestResult(status='PASS'),
            <Tool>TestResult(status='PASS'),
            <Tool>TestResult(status='FAIL'),
            <Tool>TestResult(status='UNKNOWN'),
        ]
        summary = <Tool>LogParser.summarize(results)
        assert summary['total']   == 4
        assert summary['pass']    == 2
        assert summary['fail']    == 1
        assert summary['unknown'] == 1

    def test_summarize_empty(self):
        summary = <Tool>LogParser.summarize([])
        assert summary['total'] == 0
        assert summary['error_summary'] == []
```

---

## `test_state_manager.py` Template *(only if `has_state_manager: true`)*

Ground truth: `tests/unit/lib/testtool/test_reboot/test_state_manager.py`

```python
"""
Unit tests for <Tool>StateManager.
Uses tmp_path — no real files persisted to the workspace.
"""

import json
import pytest

from lib.testtool.<package_name>.state_manager import <Tool>StateManager
from lib.testtool.<package_name>.exceptions import <Tool>StateError


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def manager(tmp_path):
    return <Tool>StateManager(str(tmp_path / 'state.json'))


@pytest.fixture
def recovering_manager(tmp_path):
    """Manager whose state file already has is_recovering=True."""
    path = tmp_path / 'state.json'
    path.write_text(
        json.dumps({'is_recovering': True, 'current_cycle': 1, 'total_cycles': 3}),
        encoding='utf-8',
    )
    return <Tool>StateManager(str(path))


# ── load ────────────────────────────────────────────────

class TestLoad:
    def test_returns_default_when_no_file(self, manager):
        state = manager.load()
        assert state['is_recovering'] is False

    def test_loads_saved_state(self, manager):
        manager.save({'is_recovering': True, 'current_cycle': 1, 'total_cycles': 2})
        assert manager.load()['is_recovering'] is True

    def test_raises_on_corrupt_json(self, tmp_path):
        bad = tmp_path / 'bad.json'
        bad.write_text('{ not json }')
        with pytest.raises(<Tool>StateError, match='Failed to load'):
            <Tool>StateManager(str(bad)).load()

    def test_back_fills_missing_keys(self, tmp_path):
        path = tmp_path / 'partial.json'
        path.write_text(json.dumps({'current_cycle': 5}), encoding='utf-8')
        state = <Tool>StateManager(str(path)).load()
        assert 'is_recovering' in state
        assert state['current_cycle'] == 5


# ── save ────────────────────────────────────────────────

class TestSave:
    def test_creates_file(self, manager, tmp_path):
        manager.save({'is_recovering': False, 'current_cycle': 0, 'total_cycles': 1})
        assert (tmp_path / 'state.json').exists()

    def test_roundtrip(self, manager):
        manager.save({'is_recovering': True, 'current_cycle': 2, 'total_cycles': 4})
        state = manager.load()
        assert state['is_recovering'] is True
        assert state['current_cycle'] == 2

    def test_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / 'a' / 'b' / 'state.json'
        <Tool>StateManager(str(deep)).save(
            {'is_recovering': False, 'current_cycle': 0, 'total_cycles': 1}
        )
        assert deep.exists()


# ── clear ───────────────────────────────────────────────

class TestClear:
    def test_removes_file(self, manager, tmp_path):
        manager.save({'is_recovering': False, 'current_cycle': 0, 'total_cycles': 1})
        manager.clear()
        assert not (tmp_path / 'state.json').exists()

    def test_no_error_when_no_file(self, manager):
        manager.clear()   # must not raise


# ── is_recovering ───────────────────────────────────────────

class TestIsRecovering:
    def test_false_when_no_file(self, manager):
        assert manager.is_recovering() is False

    def test_true_when_flag_set(self, recovering_manager):
        assert recovering_manager.is_recovering() is True

    def test_false_after_clear(self, recovering_manager):
        recovering_manager.clear()
        assert recovering_manager.is_recovering() is False

    def test_false_on_corrupt_file_no_raise(self, tmp_path):
        bad = tmp_path / 'bad.json'
        bad.write_text('not json')
        # is_recovering() must NOT raise — returns False gracefully
        assert <Tool>StateManager(str(bad)).is_recovering() is False
```

---

## Rules Summary

| Rule | Detail |
|------|--------|
| **Location** | `tests/unit/lib/testtool/test_<package_name>/` |
| **`test_exceptions.py`** | pytest style; test raise + inheritance for every exception class |
| **`test_config.py`** | pytest style; cover `get_default_config`, `validate_config`, `merge_config` |
| **`test_controller.py`** | unittest style; mock ALL external I/O; test init/status/stop/run |
| **`test_log_parser.py`** | pytest style; fixture HTML strings; test PASS/FAIL/UNKNOWN/errors/batch/summarize — only if `has_log_parser: true` |
| **`test_state_manager.py`** | pytest style; test load/save/clear/is_recovering with `tmp_path`; verify corrupt-file resilience — only if `has_state_manager: true` |
| **Wait-loop mock** | When controller has a post-subprocess `time.sleep` loop, patch `time.sleep` to set `_stop_event` on first call (use `fast_wait` fixture); do NOT pre-set `_stop_event` before start() if you need to assert subprocess was called |
| **Mocking** | Never call real executables or touch the real file system |
| **`setUp` kwargs** | Always use the minimal valid set of `__init__` params |
| **`status` checks** | Assert `None` before run, `True`/`False` after `join()` |
| **Fixtures** | Shared fixtures live in `conftest.py`; keep them minimal |
| **No real processes** | Patch `subprocess.Popen`, `os.path.exists`, `pathlib.Path.exists` as needed |
| **`__init__.py`** | Empty file, required for pytest discovery |
