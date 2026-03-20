# Chocolatey Packaging Templates Reference

Complete copy-paste templates for each file type. Replace `<id>`, `<version>`, `<ToolName>`, etc.

---

## `.nuspec` Templates

### Type B — Portable (no installer, Copy-Item)

```xml
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">
  <metadata>
    <id><TOOL_ID></id>
    <version><NUGET_VERSION></version>
    <title><ToolName> (<tool_version>)</title>
    <authors>SSD TestKit</authors>
    <requireLicenseAcceptance>false</requireLicenseAcceptance>
    <description>Portable offline wrapper for <ToolExe>.exe.
Tool version: <tool_version>
Copies from bin/installers/<ToolName>/<tool_version>/ and sets <TOOL_PATH> env var.
Requires: SSD_TESTKIT_ROOT env var pointing to the ssd-testkit repo root.</description>
    <tags><tool_id> portable offline</tags>
  </metadata>
</package>
```

### Type A — Installer (runs setup.exe / adksetup.exe)

```xml
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">
  <metadata>
    <id><TOOL_ID></id>
    <version><NUGET_VERSION></version>
    <title><ToolName> <NUGET_VERSION></title>
    <authors>SSD TestKit</authors>
    <requireLicenseAcceptance>false</requireLicenseAcceptance>
    <description>Offline wrapper for <ToolName> installer.
Calls bin/installers/<ToolName>/<NUGET_VERSION>/setup.exe quietly.
Requires: SSD_TESTKIT_ROOT env var pointing to the ssd-testkit repo root.</description>
    <tags><tool_id> offline</tags>
  </metadata>
</package>
```

---

## `chocolateyInstall.ps1` Templates

### Type B — Portable

```powershell
# chocolateyInstall.ps1  <id> <nuget_version> (<tool_version>)
# Portable tool: copies <ToolExe>.exe to $installDir, sets <TOOL_PATH> env var.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$toolVersion = "<tool_version>"          # e.g. "v20251114A"
$installDir  = "C:\tools\<ToolName>"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nUse bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$sourceDir = Join-Path $toolkitRoot "bin\installers\<ToolName>\$toolVersion"
if (-not (Test-Path $sourceDir)) {
    throw "<ToolName> source directory not found: $sourceDir`nExpected: bin/installers/<ToolName>/$toolVersion/ under SSD_TESTKIT_ROOT."
}

$exePath = Join-Path $sourceDir "<ToolExe>.exe"
if (-not (Test-Path $exePath)) {
    throw "<ToolExe>.exe not found: $exePath"
}

Write-Host "Installing <ToolName> ($toolVersion) to $installDir ..."

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

$destExe = Join-Path $installDir "<ToolExe>.exe"
if (-not (Test-Path $destExe)) {
    throw "Copy failed: <ToolExe>.exe not found at $destExe"
}

# Set machine-level env var so Python code can find the exe without hardcoding path
[Environment]::SetEnvironmentVariable('<TOOL_PATH>', $destExe, 'Machine')
Write-Host "Set <TOOL_PATH> = $destExe (Machine scope)"

Write-Host "<ToolName> ($toolVersion) installed successfully."
```

> **省略 env var**：如果工具不需要 env var（例如 burnin 透過 install_dir 固定路徑），移除 `SetEnvironmentVariable` 那兩行即可。

### Type A — Installer (setup.exe)

```powershell
# chocolateyInstall.ps1  <id> <nuget_version>
# Calls the vendor installer silently.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$buildVer    = "<nuget_version>"         # e.g. "22621" or "9.3.1000"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set."
}

$installer = Join-Path $toolkitRoot "bin\installers\<ToolName>\$buildVer\setup.exe"
if (-not (Test-Path $installer)) {
    throw "Installer not found: $installer"
}

Write-Host "Running installer: $installer"

$proc = Start-Process -FilePath $installer `
                      -ArgumentList "/quiet /norestart" `
                      -Wait -PassThru

# 0 = success, 3010 = success + reboot required
if ($proc.ExitCode -notin @(0, 3010)) {
    throw "<ToolName> installer failed with exit code $($proc.ExitCode)"
}

Write-Host "<ToolName> installed successfully (exit $($proc.ExitCode))."
```

> **WindowsADK 特殊參數**：`/features OptionId.WindowsPerformanceToolkit`（只裝 WPT，不裝全套）

---

## `chocolateyUninstall.ps1` Templates

### Type B — Portable

```powershell
# chocolateyUninstall.ps1  <id> <nuget_version> (<tool_version>)

$installDir = "C:\tools\<ToolName>"

Write-Host "Uninstalling <ToolName> from $installDir ..."

if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
    Write-Host "Removed $installDir"
} else {
    Write-Host "Directory not found (already removed?): $installDir"
}

$current = [Environment]::GetEnvironmentVariable('<TOOL_PATH>', 'Machine')
if ($current) {
    [Environment]::SetEnvironmentVariable('<TOOL_PATH>', $null, 'Machine')
    Write-Host "Cleared <TOOL_PATH> (was: $current)"
} else {
    Write-Host "<TOOL_PATH> was not set, nothing to clear."
}

Write-Host "<ToolName> uninstalled successfully."
```

### Type A — Installer

```powershell
# chocolateyUninstall.ps1  <id> <nuget_version>
# Uses choco built-in uninstall; vendor tool must register an uninstaller in registry.
# If not: use Remove-Item to clean up the install_dir explicitly.

$installDir = "<install_dir>"   # e.g. "C:\Program Files\BurnInTest"

if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
    Write-Host "Removed $installDir"
}
Write-Host "<ToolName> uninstalled."
```

---

## `package_meta.yaml` Templates

### Type B — Portable

```yaml
# lib/testtool/<tool>/package_meta.yaml
# <ToolName> — Portable tool (exe + optional drivers, no installer)

tool_name: <tool>
choco_package_id: <id>
tool_type: portable              # portable: Copy-Item, not an installer

versions:
  - version: "<nuget_version>"   # NuGet format X.Y.Z (numbers only)
    tool_version: "<tool_version>"  # From <ToolExe>.exe --version
    source_dir: "bin/installers/<ToolName>/<tool_version>"
    default: true

install_dir: "C:\\tools\\<ToolName>"
env_var: "<TOOL_PATH>"           # Remove this line if no env var needed

binaries:
  - "<ToolExe>.exe"

drivers:                         # Remove section if no kernel drivers
  - "<Driver1>.sys"
```

### Type A — Installer (single version)

```yaml
# lib/testtool/<tool>/package_meta.yaml

tool_name: <tool>
choco_package_id: <id>

versions:
  - version: "<nuget_version>"
    installer: "bin/installers/<ToolName>/<nuget_version>/setup.exe"
    default: true

install_dir: "<install_dir>"     # e.g. "C:\\Program Files\\<ToolName>"
install_args: "/quiet /norestart"

binaries:
  - "<ToolExe>.exe"
```

### Type A — Installer (multiple versions, Build Number variant)

```yaml
# lib/testtool/windows_adk/package_meta.yaml  (reference implementation)

tool_name: windows_adk
choco_package_id: windows-adk
version_id_type: build_number    # Version is a Windows Build Number

versions:
  - version: "19041"
    os_name: "Windows 10 2004"
    installer: "bin/installers/WindowsADK/19041/adksetup.exe"
    default: false

  - version: "22621"
    os_name: "Windows 11 22H2/23H2"
    installer: "bin/installers/WindowsADK/22621/adksetup.exe"
    default: true

install_args: "/quiet /norestart /features OptionId.WindowsPerformanceToolkit"
install_dir: "C:\\Program Files (x86)\\Windows Kits\\10\\Windows Performance Toolkit"
binaries:
  - "wpr.exe"
  - "wpa.exe"
```

---

## Integration Test Template

Place at `tests/integration/lib/testtool/test_<tool>/test_<tool>_workflow.py`.

Also requires:
- `tests/integration/lib/testtool/test_<tool>/__init__.py` (empty)
- `tests/integration/lib/testtool/test_<tool>/conftest.py` (see below)
- Add `requires_<tool>: ...` to `pytest.ini` markers section
- Add `"<tool>"` section to `tests/integration/Config/Config.json`

### conftest.py

```python
import os
import shutil
from pathlib import Path
import pytest
from lib.testtool.choco_manager import ChocoManager

TOOL_ID    = "<id>"
SOURCE_VER = "<tool_version>"      # matches bin/installers folder name

@pytest.fixture(scope="session")
def check_environment():
    """Skip all install/uninstall tests if choco or source files are missing."""
    if not shutil.which("choco"):
        pytest.skip("Chocolatey not installed")
    root = os.environ.get("SSD_TESTKIT_ROOT", ".")
    source = Path(root) / "bin" / "installers" / "<ToolName>" / SOURCE_VER
    if not source.exists():
        pytest.skip(f"Source directory not found: {source}")

@pytest.fixture(scope="session")
def choco_manager():
    return ChocoManager()

@pytest.fixture(scope="session")
def tool_source(request):
    root = os.environ.get("SSD_TESTKIT_ROOT", ".")
    return Path(root) / "bin" / "installers" / "<ToolName>" / SOURCE_VER
```

### test_<tool>_workflow.py

```python
import shutil
from pathlib import Path
import pytest
from lib.testtool.choco_manager import ChocoManager

TOOL_ID    = "<id>"
INSTALL_DIR = Path(r"C:\tools\<ToolName>")   # or installer path
DEST_EXE    = INSTALL_DIR / "<ToolExe>.exe"

@pytest.mark.integration
@pytest.mark.requires_<tool>
class TestChocoCliAvailability:
    def test_choco_on_path(self):
        assert shutil.which("choco") is not None

@pytest.mark.integration
@pytest.mark.requires_<tool>
class TestSourceDirectoryStructure:
    def test_source_exists(self, tool_source):
        assert tool_source.exists()

    def test_exe_present(self, tool_source):
        assert (tool_source / "<ToolExe>.exe").exists()

@pytest.mark.integration
@pytest.mark.requires_<tool>
@pytest.mark.slow
class TestChocoManagerInstall:
    @pytest.fixture(scope="class", autouse=True)
    def installed(self, choco_manager, check_environment):
        if choco_manager.is_installed(TOOL_ID):
            choco_manager.uninstall(TOOL_ID)
        result = choco_manager.install(TOOL_ID)
        assert result.success, f"Install failed: {result.error}"
        yield
        # teardown
        choco_manager.uninstall(TOOL_ID)

    def test_install_dir_exists(self):
        assert INSTALL_DIR.exists()

    def test_exe_exists(self):
        assert DEST_EXE.exists()

    def test_is_installed(self, choco_manager):
        assert choco_manager.is_installed(TOOL_ID)

@pytest.mark.integration
@pytest.mark.requires_<tool>
@pytest.mark.slow
class TestChocoManagerUninstall:
    @pytest.fixture(scope="class", autouse=True)
    def uninstalled(self, choco_manager, check_environment):
        if not choco_manager.is_installed(TOOL_ID):
            choco_manager.install(TOOL_ID)
        result = choco_manager.uninstall(TOOL_ID)
        assert result.success, f"Uninstall failed: {result.error}"
        yield

    def test_install_dir_removed(self):
        assert not INSTALL_DIR.exists()

    def test_not_installed(self, choco_manager):
        assert not choco_manager.is_installed(TOOL_ID)
```

---

## Complete Working Example — smicli

The `smicli` package is the reference implementation for **Type B (Portable)** with an env var.

| File | Path |
|------|------|
| nuspec | `bin/chocolatey/packages/smicli/2025.11.14/smicli.nuspec` |
| Install script | `bin/chocolatey/packages/smicli/2025.11.14/tools/chocolateyInstall.ps1` |
| Uninstall script | `bin/chocolatey/packages/smicli/2025.11.14/tools/chocolateyUninstall.ps1` |
| nupkg | `bin/chocolatey/packages/smicli/2025.11.14/smicli.2025.11.14.nupkg` |
| package_meta.yaml | `lib/testtool/smicli/package_meta.yaml` |
| Integration tests | `tests/integration/lib/testtool/test_smicli/` |

Key design decisions:
- `tool_version: "v20251114A"` — raw version string from `SmiCli2.exe --version`
- `version: "2025.11.14"` — NuGet-compatible numeric conversion
- `env_var: SMICLI_PATH` — set at Machine scope so `RunCard.generate_dut_info()` finds the exe without explicit path
- Kernel drivers (`WinIo64.sys`, `WinIoEx.sys`) must be in the **same directory** as the exe

## Complete Working Example — windows-adk

The `windows-adk` package is the reference implementation for **Type A (Installer)** with multiple versions.

| File | Path |
|------|------|
| nuspec | inside `bin/chocolatey/packages/windows-adk/22621/windows-adk.22621.nupkg` |
| package_meta.yaml | `lib/testtool/windows_adk/package_meta.yaml` |
| catalog.yaml | `bin/chocolatey/packages/windows-adk/catalog.yaml` |
| Integration tests | `tests/integration/lib/testtool/test_choco_manager/` |

Key design decisions:
- Version is a Windows Build Number (`22621`), stored as `22621.0.0` in NuGet (requires X.Y.Z)
- `version_id_type: build_number` in `package_meta.yaml` signals this special scheme
- `catalog.yaml` provides human-readable Build Number → Windows version mapping
- `exit 3010` (success + reboot required) treated as success in Install script
