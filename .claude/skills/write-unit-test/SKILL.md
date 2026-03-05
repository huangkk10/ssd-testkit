````skill
---
name: write-unit-test
description: Conventions and templates for writing pytest unit tests in ssd-testkit. Use when user asks to write tests, add unit tests, 補 test, 寫測試, or mentions pytest / mock / fixture / coverage.
---

# Write Unit Test — ssd-testkit

## Framework & Tools

| Item | Choice |
|------|--------|
| Test framework | `pytest` (not `unittest`) |
| Mock library | `unittest.mock` (`MagicMock`, `patch`) |
| Fixtures | `pytest` fixtures (`conftest.py` or in-file) |
| Async tests | `pytest-asyncio` (`@pytest.mark.asyncio`) |
| Coverage target | **80%** minimum per module |
| Test location | `tests/unit/lib/<toolname>/` mirroring `lib/testtool/<toolname>/` |

---

## File Naming Convention

```
tests/unit/lib/<toolname>/
├── __init__.py
├── test_config.py          # tests for config.py
├── test_controller.py      # tests for controller.py
├── test_exceptions.py      # tests for exceptions.py
├── test_process_manager.py # tests for process_manager.py (if exists)
└── test_ui_monitor.py      # tests for ui_monitor.py (if exists)
```

---

## Test Class & Function Naming

```python
class TestMyToolController:
    """Unit tests for MyToolController."""

    def test_init_with_defaults(self):          # happy path
        ...

    def test_init_with_custom_config(self):     # config merging
        ...

    def test_run_raises_on_missing_binary(self): # error path
        ...

    def test_stop_sets_event(self):             # state mutation
        ...
```

Rules:
- Class: `Test<ModuleName>` (PascalCase)
- Method: `test_<what>_<condition>` (snake_case)
- One assertion group per test method (don't test 5 things in one test)

---

## Fixture Pattern

Define shared setup in `conftest.py` or as pytest fixtures in the test file:

```python
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def default_controller():
    """Controller with default config, no external dependencies."""
    from lib.testtool.mytool.controller import MyToolController
    return MyToolController()

@pytest.fixture
def mock_process():
    """Mocked subprocess.Popen."""
    with patch("lib.testtool.mytool.process_manager.subprocess.Popen") as mock:
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"output", b"")
        mock.return_value = proc
        yield mock
```

---

## Mocking Strategy

### Mock external processes
```python
@patch("lib.testtool.burnin.process_manager.subprocess.Popen")
def test_start_launches_process(self, mock_popen):
    mock_popen.return_value.pid = 1234
    pm = BurninProcessManager(config)
    pm.start()
    mock_popen.assert_called_once()
```

### Mock file system
```python
@patch("builtins.open", mock_open(read_data="PASS: all tests"))
@patch("pathlib.Path.exists", return_value=True)
def test_parse_log_pass(self, mock_exists):
    parser = LogParser("/fake/path/result.log")
    result = parser.parse()
    assert result.status == "PASS"
```

### Mock registry (osconfig)
```python
@patch("lib.testtool.osconfig.registry_helper.winreg.OpenKey")
def test_read_registry_value(self, mock_open_key):
    mock_open_key.return_value.__enter__ = lambda s: s
    mock_open_key.return_value.__exit__ = MagicMock(return_value=False)
    ...
```

### Mock threading
```python
def test_controller_stop(self):
    ctrl = MyToolController()
    ctrl.start()
    ctrl.stop()
    ctrl.join(timeout=2)
    assert not ctrl.is_alive()
```

---

## Assertion Patterns

```python
# Value equality
assert result.status == "PASS"
assert config["timeout"] == 300

# Exception raised
with pytest.raises(MyToolTimeoutError, match="timed out after"):
    ctrl.wait_for_completion(timeout=0.001)

# Mock called correctly
mock_popen.assert_called_once_with(
    ["bit64.exe", "/run", "script.bits"],
    cwd="C:\\BurnIn",
)

# Approximate float
assert result.duration == pytest.approx(60.0, abs=1.0)
```

---

## Markers to Use

```python
@pytest.mark.unit          # always mark unit tests
@pytest.mark.slow          # if test takes >5 s even with mocks
@pytest.mark.admin         # if test needs Windows admin (rare for unit tests)
```

---

## Running & Coverage

```powershell
# Run unit tests only
pytest tests/unit/ -v

# Run tests for a single tool
pytest tests/unit/lib/burnin/ -v -s

# Run with coverage report
pytest tests/unit/ --cov=lib --cov-report=term-missing --cov-fail-under=80
```

---

## Common Mistakes to Avoid

| Wrong | Correct |
|-------|---------|
| `import unittest; class T(unittest.TestCase)` | Plain class `TestX:` with pytest |
| `self.assertEqual(a, b)` | `assert a == b` |
| `@mock.patch` without stopping | Use `with patch(...)` or `@patch` on method |
| Patching the wrong import path | Patch where the name is **used**, not where it's defined |
| Testing implementation details | Test observable behaviour / return values / exceptions |
| `print()` for debug in tests | Use `pytest -s` flag; remove before commit |
````
