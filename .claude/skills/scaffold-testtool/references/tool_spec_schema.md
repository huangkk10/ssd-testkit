# Tool Spec Schema Reference

Complete YAML schema for describing a new testtool library to the scaffold-testtool skill.

## Full Schema

```yaml
tool:
  name: "DiskInfo"                     # PascalCase — used for class names
  package_name: "diskinfo"             # snake_case — used for directory name
  description: "CrystalDiskInfo CLI wrapper for reading SMART data"
  version: "1.0.0"                     # initial __version__ value

execution:
  type: "cli"                          # cli | gui | bat | api
  executable: "DiskInfo64.exe"         # the binary/script that gets launched
  requires_install: false              # true → generate process_manager.py with install()
  has_ui: false                        # true → generate ui_monitor.py (pywinauto)
  has_script_generator: false          # true → generate script_generator.py

config_params:
  - name: "executable_path"
    type: "str"
    default: "./bin/DiskInfo/DiskInfo64.exe"
    description: "Path to DiskInfo executable"
    required: true
  - name: "output_dir"
    type: "str"
    default: "./testlog"
    description: "Directory for output logs"
  - name: "timeout_seconds"
    type: "int"
    default: 60
    description: "Maximum execution timeout in seconds"
  - name: "check_interval_seconds"
    type: "float"
    default: 2.0
    description: "Status polling interval in seconds"

result_parsing:
  method: "log_file"                   # log_file | stdout | runcard | ui
  log_file_pattern: "./testlog/*.log"  # glob pattern, only for method: log_file
  pass_pattern: "Status: OK"           # regex or plain string
  fail_pattern: "Status: FAIL|Error:"  # regex or plain string

exceptions:
  # List ONLY the additional exception names beyond the 4 always-generated ones.
  # Always generated: ConfigError, TimeoutError, ProcessError, TestFailedError
  # Conditionally generated: InstallError (requires_install), UIError (has_ui)
  - "ParseError"                       # example: add a parse-specific exception
```

---

## Field Reference

### `tool`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | PascalCase class name prefix. Used in all class names: `<name>Controller`, `<name>Config`, `<name>Error` |
| `package_name` | string | ✅ | snake_case directory and Python package name under `lib/testtool/` |
| `description` | string | ✅ | One-line description for module docstrings |
| `version` | string | ✅ | Semantic version string for `__version__` in `__init__.py` |

### `execution`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | enum | ✅ | — | `cli`: subprocess call; `gui`: subprocess + pywinauto; `bat`: .bat file via subprocess; `api`: direct Python API call |
| `executable` | string | ✅ | — | Filename of the program/script to launch |
| `requires_install` | bool | ❌ | `false` | If `true`, generates `process_manager.py` with `install()`, `is_installed()`, `uninstall()` methods |
| `has_ui` | bool | ❌ | `false` | If `true`, generates `ui_monitor.py` using pywinauto for window monitoring |
| `has_script_generator` | bool | ❌ | `false` | If `true`, generates `script_generator.py` for producing config/script files |

### `config_params`

Each entry in the list:

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ | Parameter name (snake_case). Becomes a key in `DEFAULT_CONFIG` and a class attribute |
| `type` | string | ✅ | Python type: `str`, `int`, `float`, `bool`, `list`, `dict` |
| `default` | any | ✅ | Default value. Must match the declared `type` |
| `description` | string | ✅ | Used as the inline comment in `DEFAULT_CONFIG` |
| `required` | bool | ❌ | If `true`, `validate_config()` raises `ConfigError` when missing. Default `false` |

**Standard params always included** (do not repeat in spec unless overriding defaults):

| Param | Type | Default |
|-------|------|---------|
| `timeout_seconds` | int | `300` |
| `check_interval_seconds` | float | `2.0` |
| `log_path` | str | `'./testlog/<toolname>.log'` |

### `result_parsing`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | enum | ✅ | How Pass/Fail is determined after execution |
| `log_file_pattern` | string | if method=`log_file` | Glob pattern to find the log file |
| `pass_pattern` | string | ✅ | Regex or plain string that indicates PASS |
| `fail_pattern` | string | ✅ | Regex or plain string that indicates FAIL |

**Method descriptions:**

| method | Description | Used by |
|--------|-------------|---------|
| `log_file` | Read a log file and search for patterns | DiskInfo, CDI |
| `stdout` | Capture subprocess stdout and search | CLI tools |
| `runcard` | Read RunCard.ini for PASS/FAIL status | SmartCheck |
| `ui` | Read status from the application window | BurnIN |

### `exceptions`

List any **additional** exception class names beyond the always-generated set:
- Always generated: `<Tool>Error`, `<Tool>ConfigError`, `<Tool>TimeoutError`, `<Tool>ProcessError`, `<Tool>TestFailedError`
- Auto-added if `requires_install: true`: `<Tool>InstallError`
- Auto-added if `has_ui: true`: `<Tool>UIError`

---

## Minimal Spec Examples

### CLI Tool (simplest)

```yaml
tool:
  name: "DiskInfo"
  package_name: "diskinfo"
  description: "CrystalDiskInfo wrapper"
  version: "1.0.0"
execution:
  type: "cli"
  executable: "DiskInfo64.exe"
  requires_install: false
  has_ui: false
  has_script_generator: false
config_params:
  - name: "executable_path"
    type: "str"
    default: "./bin/DiskInfo/DiskInfo64.exe"
    description: "Path to DiskInfo executable"
result_parsing:
  method: "stdout"
  pass_pattern: "Health Status: Good"
  fail_pattern: "Health Status: Caution|Bad"
exceptions: []
```

### GUI Tool with Install (full)

```yaml
tool:
  name: "BurnIn"
  package_name: "burnin"
  description: "PassMark BurnInTest wrapper"
  version: "2.0.0"
execution:
  type: "gui"
  executable: "bit.exe"
  requires_install: true
  has_ui: true
  has_script_generator: true
config_params:
  - name: "installer_path"
    type: "str"
    default: ""
    description: "Path to BurnIN installer"
    required: true
  - name: "install_path"
    type: "str"
    default: "C:\\Program Files\\BurnInTest"
    description: "Installation directory"
  - name: "test_duration_minutes"
    type: "int"
    default: 1440
    description: "Test duration in minutes"
  - name: "test_drive_letter"
    type: "str"
    default: "D"
    description: "Drive letter to test"
result_parsing:
  method: "ui"
  pass_pattern: "Test Finished"
  fail_pattern: "FAILED|error_count > 0"
exceptions:
  - "TestFailedError"
```
