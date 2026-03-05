````markdown
# Test Case Structure Rules

## Directory Layout

```
tests/integration/
├── conftest.py                           # Shared: TestCaseConfiguration, runcard_params
├── __init__.py
└── <client>/                             # e.g., client_pcie_lenovo_storagedv
    ├── __init__.py
    └── <stcXXXX_name>/                   # e.g., stc1685_burnin
        ├── Config/
        │   └── Config.json
        ├── bin/                          # Pre-placed tool binaries
        │   └── <ToolDir>/
        ├── conftest.py                   # testcase_config fixture
        ├── test_main.py                  # All test steps
        ├── README.md
        └── __init__.py
```

### `__init__.py` at every level

Every directory under `tests/integration/` that contains test files **must** have an `__init__.py`
(even if empty). This is required for:
- pytest test discovery
- VS Code Test Explorer visibility
- Proper module import resolution

Required files:
- `tests/integration/__init__.py` ✓ (already exists)
- `tests/integration/<client>/__init__.py` — create if new client
- `tests/integration/<client>/<stcXXX_name>/__init__.py` — always create

---

## File Responsibilities

### `conftest.py`

Defines a **session-scoped** `testcase_config` fixture pointing at this test case's directory.
Uses `TestCaseConfiguration` from `tests/integration/conftest.py`.

**Never skip at module level** — `pytest.skip()` in module-level conftest code will hide
all tests from VS Code Test Explorer. All skip logic belongs inside the fixture or test function.

### `test_main.py`

Single test class, inherits `BaseTestCase`. Contains:
- One `setup_test_class` class-level autouse fixture (init + teardown + RunCard)
- One `test_NN_*` method per test step
- Each step method: decorated with `@pytest.mark.order(N)` and `@step(N, "description")`
- Helper methods prefixed with `_` (e.g., `_remove_existing_burnin`, `_cleanup_test_logs`)

### `Config/Config.json`

Contains only two categories:
1. **Path params**: executable path, log directory, license path
2. **Default execution params**: duration, cycle count, intervals, timeout

Config example key-naming:
- Use lowercase with underscores for new keys (e.g., `timeout_minutes`, `log_path`)
- Legacy tools may use CamelCase keys (e.g., `ExePath`, `LogPath`) — match what
  `load_config_from_json()` expects

### `README.md`

Required sections:
1. Overview (one paragraph)
2. Test Flow (numbered list)
3. Directory Structure (tree diagram)
4. Run Instructions (PowerShell commands)
5. Config params table
6. Log locations

---

## Working Directory Rule

The test class fixture changes `os.chdir()` to the test directory at the start and restores
it at teardown. **All paths in Config.json and test code should use relative paths** starting
from the test directory (e.g., `./bin/...`, `./testlog/...`, `./Config/...`).

```python
# In setup_test_class fixture:
os.chdir(test_dir)   # at start
# ...
os.chdir(cls.original_cwd)  # at teardown (after yield)
```

### Packaged vs Development path resolution

```python
try:
    from path_manager import path_manager
    test_dir = path_manager.app_dir  # flat exe directory
except ImportError:
    test_dir = Path(__file__).parent  # test file directory
```

Always use this pattern — never hardcode absolute paths.

---

## sys.path Injection

Every `test_main.py` must add the project root to `sys.path` at the top:

```python
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[4]  # adjust depth as needed
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
```

The `parents[N]` depth depends on directory nesting:
- `tests/integration/<client>/<stcXXXX_name>/test_main.py` → `parents[4]`

---

## Pytest Markers Registration

Every marker used on a test class must be registered in `pytest.ini`:

```ini
[pytest]
markers =
    client_lenovo: Lenovo client tests
    interface_pcie: PCIe interface tests
    project_storagedv: StorageDV project tests
    feature_burnin: BurnIN feature tests
    slow: Tests taking more than 30 minutes
```

The project uses `--strict-markers`, so **unregistered markers cause collection errors**.

---

## Test Step Ordering

Use `pytest-ordering` via `@pytest.mark.order(N)`:
- Steps start at 1, not 0
- Numbers are contiguous integers
- One number per test method
- `@step(N, "description")` must match the `@pytest.mark.order(N)` number

**Correct:**
```python
@pytest.mark.order(1)
@step(1, "Setup precondition")
def test_01_precondition(self): ...

@pytest.mark.order(2)
@step(2, "Install tool")
def test_02_install(self): ...
```

---

## Log Cleanup Pattern

Always clean up previous test logs in `test_01_precondition`:

```python
def _cleanup_test_logs(self):
    Path('./testlog').mkdir(parents=True, exist_ok=True)
    cleanup_directory('./testlog/CDILog', 'CDI log directory', logger)
    BurnInController.cleanup_logs(testlog_path='./testlog')
    SmartCheckController.cleanup_logs(testlog_path='./testlog')
    cleanup_directory(self.config.get('log_path', './log/STC-XXXX'), 'test log', logger)
```

Use `framework.test_utils.cleanup_directory()` for generic directories.
Use `<Controller>.cleanup_logs()` for tool-specific log cleanup (if the controller provides it).

````
