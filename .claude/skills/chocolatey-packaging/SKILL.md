---
name: chocolatey-packaging
description: Package and manage tools as offline Chocolatey nupkg for the ssd-testkit project. Use when user asks to package a tool with chocolatey, 打包工具, 建立 nupkg, 新增 choco package, 升版, 或如何讓工具可以 choco install/uninstall. Also covers package_meta.yaml, ChocoManager, and integration test verification.
---

# Chocolatey Packaging Skill

Package Windows tools as offline Chocolatey `.nupkg` for the ssd-testkit project.
All packages run in **offline mode** (no internet required on target machines).

## Key Concepts

| Term | 說明 |
|------|------|
| **nupkg** | NuGet/Chocolatey 套件主體（本質是 zip），內含 `.nuspec` + `tools/` 腳本 |
| **nuspec** | XML 描述檔：`id`, `version`, `description` |
| **chocolateyInstall.ps1** | 安裝腳本：複製檔案 or 執行安裝程式 |
| **chocolateyUninstall.ps1** | 移除腳本：清理目錄、清除 env var |
| **package_meta.yaml** | Python 側的版本映射表（`ChocoManager` 讀取） |
| **ChocoManager** | `lib/testtool/choco_manager.py` — Python API 呼叫 choco |
| **SSD_TESTKIT_ROOT** | 安裝腳本透過此 env var 找到大型安裝檔，由 `install_packages.ps1` 注入 |

---

## 四階段邊界（重要）

1. 打包（Pack）：`choco pack` 產生 `.nupkg`
2. 上傳（Upload）：`tool-manager/upload_tools_to_nexus.ps1` 上傳 `.nupkg` 到 Nexus、zip 備份到 NAS
3. 準備（Prepare）：`tool-manager/prepare_testcase.ps1` 下載 `.nupkg` 並補齊 `bin/installers/` 檔案
4. 安裝（Install）：`bin/chocolatey/scripts/install_packages.ps1` 或 `ChocoManager.install()`

> `prepare_testcase.ps1` 不會執行 `choco install`。

---

## Source Of Truth

- `lib/testtool/tools-registry.yaml`：tool-manager 流程的版本與來源路徑主資料（`version`, `source_dir`, `nexus_path`）
- `lib/testtool/<tool>/package_meta.yaml`：Python 端 `ChocoManager` 的版本映射來源

## Two Tool Types

### Type A — Installer (有安裝程式)
範例：`windows-adk`、`burnin`、`cdi`

```
chocolateyInstall.ps1 → 執行 adksetup.exe / setup.exe
chocolateyUninstall.ps1 → choco 原生卸載 or 自訂 Uninstall
```

### Type B — Portable (無安裝程式，直接複製)
範例：`smicli`、`pwrtest`

```
chocolateyInstall.ps1 → Copy-Item 整個目錄 + 設定 env var
chocolateyUninstall.ps1 → Remove-Item + 清除 env var
```

---

## Directory Layout

```
bin/
├── chocolatey/
│   ├── installer/
│   │   └── chocolatey.2.7.0.nupkg        # Chocolatey 本體（已備齊）
│   ├── packages/
│   │   └── <tool-id>/
│   │       └── <version>/
│   │           ├── <tool-id>.<version>.nupkg    ← 主要產出
│   │           ├── <tool-id>.<version>.sha256   ← 校驗雜湊
│   │           ├── <tool-id>.nuspec             ← 打包前的來源描述檔
│   │           └── tools/
│   │               ├── chocolateyInstall.ps1
│   │               └── chocolateyUninstall.ps1
│   ├── config/
│   │   ├── packages.config    # 宣告要安裝的工具與版本
│   │   ├── sources.config
│   │   └── environment.config
│   └── scripts/
│       ├── install_packages.ps1   # 批次安裝（自動注入 SSD_TESTKIT_ROOT）
│       └── install_choco.ps1
└── installers/                    # 廠商原始大型安裝檔（git-ignored）
    └── <ToolName>/
        └── <version_subfolder>/
            └── (exe / sys / pdb ...)

lib/testtool/
└── <tool>/
    └── package_meta.yaml          # Python 側版本映射表
```

> **重要**：`bin/installers/` 完全 git-ignored，大型安裝檔不 commit。
> nupkg 只含薄包裝腳本，安裝時透過 `SSD_TESTKIT_ROOT` 找到安裝檔。

---

## Step-by-Step: 打包一個新工具

### Step 1 — 確認工具類型與版本

```powershell
# 確認版本
.\<ToolExe>.exe --version
# 確認是 Installer 還是 Portable（有沒有 setup.exe / installer）
```

### Step 2 — 建立目錄

```powershell
$toolId  = "mytool"         # Chocolatey id (lowercase, hyphen ok)
$version = "1.2.3"          # NuGet 格式，必須是 X.Y.Z（純數字）
New-Item -ItemType Directory "bin/chocolatey/packages/$toolId/$version/tools" -Force
```

> **版本號規則**：NuGet 版本只允許數字，例如 `v20251114A` → `2025.11.14`；
> 工具自身版本字串記錄在 `package_meta.yaml` 的 `tool_version` 欄位。

### Step 3 — 撰寫 nuspec

**For detailed templates**, see `references/packaging_templates.md`

```xml
<!-- bin/chocolatey/packages/<id>/<version>/<id>.nuspec -->
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">
  <metadata>
    <id>mytool</id>
    <version>1.2.3</version>
    <title>MyTool (v1.2.3)</title>
    <authors>SSD TestKit</authors>
    <requireLicenseAcceptance>false</requireLicenseAcceptance>
    <description>Brief description. Requires SSD_TESTKIT_ROOT env var.</description>
    <tags>mytool offline</tags>
  </metadata>
</package>
```

> 本專案常見結構為 `bin/chocolatey/packages/<id>/<version>/<id>.nuspec`，
> 並在相同 `<version>` 目錄輸出 `<id>.<version>.nupkg`。

### Step 4 — 撰寫 chocolateyInstall.ps1

**Type B (Portable)**：

```powershell
$toolVersion = "v1.2.3"
$installDir  = "C:\tools\MyTool"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) { throw "SSD_TESTKIT_ROOT is not set." }

$sourceDir = Join-Path $toolkitRoot "bin\installers\MyTool\$toolVersion"
if (-not (Test-Path $sourceDir)) { throw "Source not found: $sourceDir" }

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

# 若需要 env var（如 SMICLI_PATH），在此設定：
[Environment]::SetEnvironmentVariable('MYTOOL_PATH', "$installDir\mytool.exe", 'Machine')
Write-Host "MyTool installed to $installDir"
```

**Type A (Installer)**：

```powershell
$buildVer    = "22621"
$toolkitRoot = $env:SSD_TESTKIT_ROOT
if (-not $toolkitRoot) { throw "SSD_TESTKIT_ROOT is not set." }

$installer = Join-Path $toolkitRoot "bin\installers\MyTool\$buildVer\setup.exe"
if (-not (Test-Path $installer)) { throw "Installer not found: $installer" }

$proc = Start-Process -FilePath $installer -ArgumentList "/quiet /norestart" -Wait -PassThru
if ($proc.ExitCode -notin @(0, 3010)) { throw "Installer failed: exit $($proc.ExitCode)" }
# exit 3010 = success, reboot required
```

### Step 5 — 撰寫 chocolateyUninstall.ps1

**Type B (Portable)**：

```powershell
$installDir = "C:\tools\MyTool"
if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }
[Environment]::SetEnvironmentVariable('MYTOOL_PATH', $null, 'Machine')
Write-Host "MyTool uninstalled."
```

### Step 6 — 打包 nupkg

```powershell
cd bin/chocolatey/packages/<id>/<version>
choco pack <id>.nuspec
# 產出：<id>.<version>.nupkg
```

### Step 7 — 計算 SHA256

```powershell
CertUtil -hashfile <id>.<version>.nupkg SHA256 | Out-File <id>.<version>.sha256
```

### Step 8 — 建立 package_meta.yaml

**For full schema**, see `references/packaging_templates.md`

> ⚠️ **CRITICAL — Top-level placement rule:**
> `install_dir`, `env_var`, `binaries` **MUST be at the top level** of the YAML file.
> `_inject_env_from_meta()` in `tool_installer.py` reads these keys from `meta.get(...)` directly.
> Placing them inside `versions[]` entries causes silent failure — the env var is never injected,
> the tool's exe_path resolves to a relative path, and the process launch fails.

```yaml
# lib/testtool/<tool>/package_meta.yaml

tool_name: mytool
choco_package_id: mytool
tool_type: portable          # portable | installer

versions:
  - version: "1.2.3"         # NuGet 版本
    tool_version: "v1.2.3"   # 工具自身版本（--version 輸出）
    source_dir: "bin/installers/MyTool/v1.2.3"
    default: true
    # ↑ versions[] entries: version/tool_version/source_dir/default ONLY
    # ↑ DO NOT put install_dir/env_var/binaries inside versions[]

install_dir: "C:\\tools\\MyTool"   # TOP LEVEL — read by _inject_env_from_meta()
env_var: "MYTOOL_PATH"             # TOP LEVEL — injected as full path: install_dir\binaries[0]
binaries:
  - "mytool.exe"                   # TOP LEVEL — first entry used as env var target
```

> ⚠️ **CRITICAL — env var value is the FULL EXE PATH, not a directory:**
> `_inject_env_from_meta()` injects `env_var = install_dir\binaries[0]` (e.g. `C:\tools\MyTool\mytool.exe`).
> In the controller's `__init__`, consume the env var **directly** — do NOT `os.path.join()` it with the exe name again:
>
> ```python
> # ✅ Correct
> resolved = exe_path or os.environ.get('MYTOOL_PATH', '') or DEFAULT_EXE_PATH
>
> # ❌ Wrong — doubles the exe name: C:\tools\MyTool\mytool.exe\mytool.exe
> resolved = exe_path or os.path.join(os.environ.get('MYTOOL_PATH', ''), 'mytool.exe')
> ```

### Step 9 — 更新 packages.config

```xml
<!-- bin/chocolatey/config/packages.config -->
<packages>
  <package id="mytool" version="1.2.3" />
</packages>
```

### Step 10 — 上傳與準備流程串接

```powershell
# 上傳 nupkg 到 Nexus + 備份 installer zip 到 NAS
.\tool-manager\upload_tools_to_nexus.ps1

# 新機器準備 testcase 工具檔案（下載 nupkg + 解壓 installer）
.\tool-manager\prepare_testcase.ps1 stc1685_burnin
```

如需真正安裝工具，請再執行：

```powershell
.\bin\chocolatey\scripts\install_packages.ps1
```

### Step 11 — 更新 /readme 頁面

上傳完成後，執行以下指令把新工具加入 `https://10.252.170.171/readme`：

```powershell
python tools\update_nexus_readme.py `
    --name "My Tool Display Name" `
    --id   mytool `
    --version 1.2.3
```

腳本會自動完成三件事：
1. 在 GitLab `packages/windows/bootstrap/README.html` 插入新的工具列和更新「一次安裝全部」指令
2. Commit 到 GitLab (`chunwei/packages-win-linux`)
3. SSH 到 Nexus server (`owner@10.252.170.171`) 執行 `git pull`（bind-mount 即時生效，不需 reload nginx）

> 移除工具時：`python tools\update_nexus_readme.py --remove --id mytool --version 1.2.3`
>
> 乾跑預覽（不 commit）：加上 `--dry-run`

---

## Testing the Package

### Test 1 — 語法驗證（不實際安裝）

```powershell
choco pack bin/chocolatey/packages/<id>/<version>/<id>.nuspec
# 成功：產出 .nupkg，無錯誤
```

### Test 2 — 本地安裝測試

```powershell
# 設定 SSD_TESTKIT_ROOT（install_packages.ps1 會自動注入，手動測試時需自己設）
$env:SSD_TESTKIT_ROOT = "C:\automation\ssd-testkit"

choco install <id> --source "bin/chocolatey/packages/<id>/<version>" --yes --no-progress
# 驗證：安裝目錄存在、binary 存在、env var 正確（若有）
```

### Test 3 — 移除測試

```powershell
choco uninstall <id> --yes
# 驗證：安裝目錄消失、env var 清除（若有）
```

### Test 4 — Python 整合測試（ChocoManager）

```python
from lib.testtool.choco_manager import ChocoManager
mgr = ChocoManager()
result = mgr.install("mytool")
assert result.success, result.error
assert mgr.is_installed("mytool")
result = mgr.uninstall("mytool")
assert result.success
```

### Test 5 — Integration Test (pytest)

Tests go in `tests/integration/lib/testtool/test_<toolname>/`.
**For complete templates**, see `references/packaging_templates.md`

---

## Known Tools Reference

| Tool ID | Type | Versions | package_meta.yaml | nupkg 位置 |
|---------|------|----------|-------------------|------------|
| `windows-adk` | installer | 19041, 22000, 22621, **26100.0.0** | `lib/testtool/windows_adk/` | `bin/chocolatey/packages/windows-adk/26100.0.0/` |
| `smicli` | portable | **2026.2.13** | `lib/testtool/smicli/` | `bin/chocolatey/packages/smicli/2026.2.13/` |
| `playwright-browsers` | portable | **1.58.0** | `lib/testtool/playwright_browsers/` | `bin/chocolatey/packages/playwright-browsers/1.58.0/` |
| `net-7-sdk` | installer | **7.0.410** | `lib/testtool/net_7_sdk/` | `bin/chocolatey/packages/net-7-sdk/7.0.410/` |
| `cdi` | portable | **8.17.13** | `lib/testtool/cdi/` | `bin/chocolatey/packages/cdi/8.17.13/` |
| `smiwintools` | portable | **2026.2.13.1** | `lib/testtool/smartcheck/` | `bin/chocolatey/packages/smiwintools/2026.2.13.1/` |
| `phm` | installer | **4.22.0** | `lib/testtool/phm/` | `bin/chocolatey/packages/phm/4.22.0/` |
| `burnin` | installer | **10.2.1004** | `lib/testtool/burnin/` | `bin/chocolatey/packages/burnin/10.2.1004/` |
| `chrome` | installer | **147.0.7727.138** | `lib/testtool/chrome/` | `bin/chocolatey/packages/chrome/147.0.7727.138/` |
| `pwrtest` | portable | 1.9.0 | 尚未建立 | 尚未建立 |

**已完成工具的完整範例**：see `references/packaging_templates.md`

---

## ChocoManager Python API

```python
from lib.testtool.choco_manager import ChocoManager

mgr = ChocoManager()

# 安裝（省略 version 時用 package_meta.yaml 的 default: true）
result = mgr.install("windows-adk")
result = mgr.install("windows-adk", "22621.0.0")

# 移除
result = mgr.uninstall("windows-adk")

# 查詢
mgr.is_installed("windows-adk")       # -> bool
mgr.get_installed_version("windows-adk")  # -> str | None
```

`InstallResult` fields: `success`, `tool_id`, `version`, `exit_code`, `output`, `error`

---

## Version Upgrade Flow

新版本工具上線步驟：

```
1. 下載新版執行檔 → 放入 bin/installers/<Tool>/<new_version>/
2. 建立 bin/chocolatey/packages/<id>/<new_version>/ 目錄
3. 複製並修改 nuspec、chocolateyInstall.ps1、chocolateyUninstall.ps1
4. choco pack → 產出新 nupkg
5. 計算新 sha256
6. 更新 lib/testtool/<tool>/package_meta.yaml：新增 version 條目，調整 default: true
7. 更新 bin/chocolatey/config/packages.config 中的 version
8. 跑 Test 2–4 驗證
9. .\tool-manager\upload_tools_to_nexus.bat  （上傳 nupkg + installer zip）
10. python tools\update_nexus_readme.py --name "<Display Name>" --id <id> --version <ver>  （更新 /readme 頁面）
11. git commit，tag 格式：choco/<id>@<version>
```

---

## Common Errors

| 錯誤 | 原因 | 解法 |
|------|------|------|
| `SSD_TESTKIT_ROOT is not set` | 直接呼叫 `choco install` 而非透過 `install_packages.ps1` | 手動 `$env:SSD_TESTKIT_ROOT = "..."` 再執行 |
| NuGet version `v20251114A` invalid | 版本號含英文字母 | 轉換為純數字格式，如 `2025.11.14` |
| `choco install` source not found | nupkg 路徑需指向**含 nupkg 的目錄**，而非套件根目錄 | `--source "packages/<id>/<version>"`，不能是 `packages/<id>/` |
| `choco uninstall` 不執行 `chocolateyUninstall.ps1` | nupkg 未安裝到 choco 本地 DB | 確認 `choco list` 顯示該工具已安裝 |
| SHA256 檔案格式錯誤 | `CertUtil` 輸出含標頭行 | 只取第二行（hash 值）或用 `Get-FileHash` |
