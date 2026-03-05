````skill
---
name: build-and-test
description: How to install dependencies, run tests, and build the release EXE for ssd-testkit. Use when user asks 怎麼跑 test、怎麼 build、怎麼打包、how to run pytest、how to build RunTest.exe, or mentions build / package / release.
---

# Build and Test — ssd-testkit

## 1. Prerequisites

- Windows 10/11, Python 3.10+
- Run terminal / PowerShell **as Administrator** (hardware tests require elevation)
- `.venv` activation:

```powershell
# From repo root
.\.venv\Scripts\Activate.ps1
```

If `.venv` doesn't exist yet:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Running Tests

### Run all tests
```powershell
pytest
```

### Run only unit tests (fast, no hardware)
```powershell
pytest tests/unit/ -m unit
```

### Run only integration tests
```powershell
pytest tests/integration/ -m integration
```

### Run a specific test file
```powershell
pytest tests/integration/client_pcie_lenovo_storagedv/test_burnin.py -v
```

### Run with a specific marker filter
```powershell
pytest -m "not hardware and not slow"
```

### Run with verbose + show captured output
```powershell
pytest -v -s
```

### Run smoke / verification scripts (standalone, not pytest)
```powershell
python tests/verification/phm/smoke_phm_collector_steps.py
```

---

## 3. pytest Markers Reference

| Marker | Meaning |
|--------|---------|
| `unit` | Fast unit tests, no hardware |
| `integration` | Requires real hardware setup |
| `admin` | Requires Administrator privileges |
| `hardware` | Directly accesses hardware I/O |
| `slow` | Takes >60 s to complete |
| `real` | Requires real hardware (no mock) |
| `real_bat` | Requires real `.bat` execution |
| `client_lenovo` | Lenovo-specific customer tests |

---

## 4. Building the Release EXE

### One-click build (recommended)
```powershell
cd packaging
.\build.bat
```

### Build with Python directly
```powershell
cd packaging
python build.py
```

### Build with custom config
```powershell
python build.py --config build_config.yaml
```

### Output location
```
packaging/release/<tag>/
├── RunTest.exe         # Self-contained EXE (includes Python + all deps)
├── bin/                # Bundled test tool binaries
├── Config/             # JSON test configs
└── tests/              # Embedded test modules
```

---

## 5. RunTest.exe Usage (on DUT)

```powershell
# Run all bundled tests
.\RunTest.exe

# Run specific test by ID
.\RunTest.exe --test stc1685

# List available tests
.\RunTest.exe --list
```

---

## 6. Checking Build Output

```powershell
python packaging/check_build.py
```

This verifies the release folder has all expected files and binaries.

---

## 7. Logs

- Test run logs: `testlog/` (created automatically by pytest)
- Build logs: `packaging/log/log.txt` and `packaging/log/log.err`
- Runtime logs (from EXE): `log/log.txt` and `log/log.err`
````
