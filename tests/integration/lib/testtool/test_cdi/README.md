# CDI Integration Tests

Real end-to-end tests for `lib/testtool/cdi/` against an actual running CrystalDiskInfo (DiskInfo64.exe).

## Requirements

| Item | Detail |
|------|--------|
| DiskInfo64.exe | Present at `bin/CrystalDiskInfo/DiskInfo64.exe` (or override below) |
| Physical disk | At least one disk visible to CrystalDiskInfo |
| OS | Windows 10 / 11 |
| Python packages | `pywinauto`, `psutil`, `pyperclip` |
| Privilege | Run as **Administrator** (DiskInfo64 needs raw-disk access) |
| Display | Desktop / virtual display for GUI automation |

## Configuration

All paths can be overridden with environment variables:

```powershell
$env:CDI_EXE_PATH      = "C:\tools\CrystalDiskInfo\DiskInfo64.exe"
$env:CDI_LOG_DIR       = "C:\testlog\cdi_run"
$env:CDI_DRIVE_LETTER  = "C:"
$env:CDI_TIMEOUT       = "120"
```

## Running the Tests

```powershell
# Run only CDI integration tests
pytest tests/integration/lib/testtool/test_cdi/ -v -m "integration"

# Run with custom timeout
$env:CDI_TIMEOUT = "180"
pytest tests/integration/lib/testtool/test_cdi/ -v -m "integration"

# Skip integration tests (run only unit tests)
pytest -m "not integration"
```

## Test Map

| Test | What it actually does |
|------|-----------------------|
| `test_full_workflow_creates_txt` | Starts DiskInfo64.exe, exports DiskInfo.txt via Ctrl+T |
| `test_full_workflow_creates_json` | Verifies text log is parsed into valid DiskInfo.json |
| `test_full_workflow_controller_status_true` | Confirms `controller.status is True` after success |
| `test_full_workflow_json_has_cdi_version` | Checks CrystalDiskInfo version field in JSON |
| `test_log_prefix_applied` | With `prefix='Before_'`, files must be `Before_DiskInfo.*` |
| `test_json_disk_has_model` | Every disk entry in JSON has a non-empty Model string |
| `test_json_disk_has_smart` | Every disk has ≥ 1 S.M.A.R.T. attribute |
| `test_get_drive_info_returns_model` | `get_drive_info('C:', '', 'Model')` returns real model name |
| `test_get_smart_value_returns_int` | `get_smart_value()` returns integer raw value |
| `test_smart_no_increase_between_snapshots` | Two runs back-to-back; stable attributes must not increase |
| `test_bad_exe_path_sets_status_false` | Wrong exe path → `status=False`, no hang |

## Output Files

Each test run creates a unique subdirectory under `CDI_LOG_DIR`:

```
testlog/
└── CDI_integration_<timestamp>/
    └── run_<ms>/
        ├── DiskInfo.txt
        ├── DiskInfo.json
        └── DiskInfo_<disk_name>.png
```

Files are intentionally kept after each run for manual inspection.
