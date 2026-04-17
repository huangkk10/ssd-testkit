# STC-1067: WinPVT Standby Critical

## 概述 (Overview)

Validates SSD health under HP WinPVT Standby stress at the Critical level.
Captures a CDI SMART baseline before the run, executes WinPVT Standby Critical,
then compares SMART attributes to detect unexpected attribute changes (e.g., Unsafe Shutdowns).

## 測試流程 (Test Flow)

| Step | Name | Description |
|------|------|-------------|
| 01 | Precondition | Clean testlog, remove stale reboot state |
| 02 | Install Tools | Install WinPVT, SmiCli, CDI via Chocolatey |
| 03 | Apply OsConfig | Disable System Restore / MemDiag / McAfee / Fast Startup; enable auto login |
| 04 | Clean Environment | Reboot for clean platform environment |
| 05 | CDI Before | Capture SMART baseline (Before_ prefix) |
| 06 | Run WinPVT Standby | Execute WinPVT Standby Critical scenario |
| 07 | CDI After | Capture post-test SMART snapshot (After_ prefix) |
| 08 | SMART Compare | Verify Unsafe Shutdowns unchanged; must-be-zero attrs == 0 |

## 目錄結構 (Directory Structure)

```
stc1067_winpvt_standby_critical/
├── Config/
│   ├── Config.json       # Tool paths + execution parameters
│   ├── osconfig.yaml     # OS configuration (power, tasks, auto-login)
│   └── tools.yaml        # Tool installation declarations
├── conftest.py           # testcase_config fixture
├── test_main.py          # Main test class (all steps)
├── README.md             # This file
└── __init__.py           # Empty, required for pytest discovery
```

## 環境需求 (Requirements)

- Windows OS with Administrator privileges
- WinPVT 11.16.0 installer: `bin/installers/winpvt/11.16.0/WinPVT.exe`
- Chocolatey package: `bin/chocolatey/packages/winpvt/11.16.0/winpvt.11.16.0.nupkg`
- CDI (CrystalDiskInfo): `C:\tools\CrystalDiskInfo\DiskInfo64.exe`
- SmiCli2.exe for RunCard DUT info collection

## 執行方式 (Run)

```powershell
# Full run (requires hardware + installed tools)
pytest tests/integration/test_case/stc1067_winpvt_standby_critical/test_main.py -v -s

# Collect test methods without executing
pytest tests/integration/test_case/stc1067_winpvt_standby_critical/test_main.py --collect-only
```

## 環境變數 (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `SSD_TESTKIT_AUTO_LOGIN_PASSWORD` | *(empty)* | Password for auto admin logon after reboot |
| `TOOL_LOG_DIR` | `./testlog` | Override base directory for log output |
