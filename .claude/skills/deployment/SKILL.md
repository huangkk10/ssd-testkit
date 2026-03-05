````skill
---
name: deployment
description: How to build and deploy a ssd-testkit release — from tagging through building the EXE, verifying the package, and delivering to field engineers. Use when user asks to deploy, release, package, ship, 打包, 出包, 交付, or mentions RunTest.exe delivery.
---

# Deployment — ssd-testkit

## Deployment Model

ssd-testkit ships as a **single self-contained Windows EXE** (`RunTest.exe`).  
There is no server or CI/CD remote deployment — the EXE is built locally, then delivered to the DUT (Device Under Test) machine by field engineers.

---

## Step 1 — Pre-build Checklist

Before building, verify:

- [ ] All tests pass:
  ```powershell
  pytest tests/unit/ -v
  ```
- [ ] `requirements.txt` is up to date
- [ ] `packaging/build_config.yaml` includes the correct test IDs, bin paths, and config files for this release
- [ ] Release tag / version is set in `build_config.yaml`
- [ ] Required binaries exist in `tests/integration/<scenario>/bin/`  
  (binaries are NOT committed to git; must be present locally before build)
- [ ] Running in an Administrator terminal

---

## Step 2 — Build the EXE

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# One-click build
cd packaging
.\build.bat
```

Or manually:
```powershell
cd packaging
python build.py
```

With a specific config:
```powershell
python build.py --config build_config.yaml
```

Build logs are written to:
- `packaging/log/log.txt`
- `packaging/log/log.err`

---

## Step 3 — Verify the Build

```powershell
python packaging/check_build.py
```

This checks:
- EXE exists and is non-zero bytes
- All expected `bin/` files are bundled
- All `Config/` JSON files are present
- No import errors at EXE startup (dry-run)

Manually spot-check the release folder:
```
packaging/release/<tag>/
├── RunTest.exe         ← must exist
├── bin/                ← must contain all required tool binaries
├── Config/             ← must contain test JSON configs
└── tests/              ← embedded test modules
```

---

## Step 4 — Smoke Test the EXE

Run the built EXE on the **build machine** first (no hardware required):

```powershell
cd packaging\release\<tag>
.\RunTest.exe --list     # must print available tests without error
```

If an integration smoke test environment is available:
```powershell
.\RunTest.exe --test stc1685 --dry-run
```

---

## Step 5 — Package for Delivery

```powershell
# Create a ZIP of the release folder
Compress-Archive -Path packaging\release\<tag>\* `
    -DestinationPath packaging\release\<tag>.zip
```

Naming convention:
```
STC-<number>_<test_name>_<YYYYMMDD>.zip
# Example: STC-1685_Burnin_test_20260224.zip
```

Already-released packages are stored in:
```
packaging/release/
└── STC-1685_Burnin_test_20260224/
```

---

## Step 6 — Deliver to Field Engineer

1. Copy the ZIP to the target DUT via network share, USB, or secure file transfer
2. Provide the field engineer with:
   - The ZIP file
   - Required external binaries checklist (if not bundled)
   - Run instructions:
     ```
     1. Extract ZIP
     2. Run as Administrator: .\RunTest.exe
     3. Logs will appear in testlog\ folder
     ```

---

## Rollback

There is no automated rollback — field engineers keep the previous ZIP.  
To re-deploy an older version, provide the previous release ZIP.

---

## Updating `build_config.yaml`

When adding a new test or binary to a release, update `packaging/build_config.yaml`:

```yaml
tests:
  - id: stc1685
    path: tests/integration/client_pcie_lenovo_storagedv

binaries:
  - src: tests/integration/client_pcie_lenovo_storagedv/bin/bit64.exe
    dest: bin/bit64.exe

configs:
  - src: tests/integration/client_pcie_lenovo_storagedv/Config/
    dest: Config/
```

After editing, re-run the build (Step 2) and verify (Step 3).
````
