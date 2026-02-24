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
└── test_ui_monitor.py        # if ui_monitor.py exists
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

Uses **unittest** style (`class TestX(unittest.TestCase)` + `setUp`/`tearDown`).  
All external dependencies (subprocess, file system, sub-components) must be **mocked**.

```python
"""
Unit tests for <Tool> Controller.
Tests <Tool>Controller with mocked dependencies.
"""

import unittest
from unittest.mock import Mock, patch
import threading

from lib.testtool.<package_name>.controller import <Tool>Controller
from lib.testtool.<package_name>.exceptions import (
    <Tool>ConfigError,
    <Tool>TimeoutError,
    <Tool>ProcessError,
)


class Test<Tool>Controller(unittest.TestCase):

    def setUp(self):
        """Set up minimal valid kwargs for __init__."""
        self.valid_kwargs = {
            'executable_path': './bin/tool.exe',
            'timeout_seconds': 60,
        }
        # Patch file system checks if __init__ validates paths
        self._patch_exists = patch('pathlib.Path.exists', return_value=True)
        self._patch_exists.start()

    def tearDown(self):
        self._patch_exists.stop()

    # ----- Initialization -----

    def test_init_sets_defaults(self):
        ctrl = <Tool>Controller(**self.valid_kwargs)
        self.assertEqual(ctrl._config['timeout_seconds'], 60)
        self.assertIsNone(ctrl.status)
        self.assertEqual(ctrl.error_count, 0)

    def test_is_thread(self):
        ctrl = <Tool>Controller(**self.valid_kwargs)
        self.assertIsInstance(ctrl, threading.Thread)

    def test_init_invalid_config_raises(self):
        with self.assertRaises(<Tool>ConfigError):
            <Tool>Controller(unknown_param='bad')

    # ----- set_config -----

    def test_set_config_updates_value(self):
        ctrl = <Tool>Controller(**self.valid_kwargs)
        ctrl.set_config(timeout_seconds=120)
        self.assertEqual(ctrl._config['timeout_seconds'], 120)

    def test_set_config_invalid_key_raises(self):
        ctrl = <Tool>Controller(**self.valid_kwargs)
        with self.assertRaises(<Tool>ConfigError):
            ctrl.set_config(bad_key='value')

    # ----- status property -----

    def test_status_initially_none(self):
        ctrl = <Tool>Controller(**self.valid_kwargs)
        self.assertIsNone(ctrl.status)

    # ----- stop -----

    def test_stop_sets_event(self):
        ctrl = <Tool>Controller(**self.valid_kwargs)
        self.assertFalse(ctrl._stop_event.is_set())
        ctrl.stop()
        self.assertTrue(ctrl._stop_event.is_set())

    # ----- run (mocked execution) -----

    @patch.object(<Tool>Controller, '_execute_test')
    def test_run_pass(self, mock_execute):
        """run() sets status=True when _execute_test succeeds."""
        mock_execute.return_value = None
        ctrl = <Tool>Controller(**self.valid_kwargs)
        # Manually set status to simulate pass inside _execute_test
        def fake_execute():
            ctrl._status = True
        mock_execute.side_effect = fake_execute

        ctrl.start()
        ctrl.join(timeout=5)
        self.assertTrue(ctrl.status)

    @patch.object(<Tool>Controller, '_execute_test')
    def test_run_timeout(self, mock_execute):
        """run() sets status=False on TimeoutError."""
        mock_execute.side_effect = <Tool>TimeoutError("timed out")
        ctrl = <Tool>Controller(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)

    @patch.object(<Tool>Controller, '_execute_test')
    def test_run_process_error(self, mock_execute):
        """run() sets status=False on ProcessError."""
        mock_execute.side_effect = <Tool>ProcessError("proc failed")
        ctrl = <Tool>Controller(**self.valid_kwargs)
        ctrl.start()
        ctrl.join(timeout=5)
        self.assertFalse(ctrl.status)


if __name__ == '__main__':
    unittest.main()
```

---

## Rules Summary

| Rule | Detail |
|------|--------|
| **Location** | `tests/unit/lib/testtool/test_<package_name>/` |
| **`test_exceptions.py`** | pytest style; test raise + inheritance for every exception class |
| **`test_config.py`** | pytest style; cover `get_default_config`, `validate_config`, `merge_config` |
| **`test_controller.py`** | unittest style; mock ALL external I/O; test init/status/stop/run |
| **Mocking** | Never call real executables or touch the real file system |
| **`setUp` kwargs** | Always use the minimal valid set of `__init__` params |
| **`status` checks** | Assert `None` before run, `True`/`False` after `join()` |
| **Fixtures** | Shared fixtures live in `conftest.py`; keep them minimal |
| **No real processes** | Patch `subprocess.Popen`, `os.path.exists`, `pathlib.Path.exists` as needed |
| **`__init__.py`** | Empty file, required for pytest discovery |
