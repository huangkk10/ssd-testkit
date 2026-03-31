---
name: tool-manager
description: Manage tool preparation, upload, and download for ssd-testkit. Use when user asks about 準備工具, 下載 tool, 上傳 nupkg, 上傳到 Nexus, 上傳到 NAS, installer zip, prepare_testcase, upload_tools_to_nexus, tools-registry.yaml, bin\installers, bin\chocolatey\packages, or 如何讓新機器取得工具.
---

# Tool Manager Skill

管理 ssd-testkit 所需工具的準備、上傳與下載流程。

---

## 系統架構

```
[開發機 / 有完整 bin\]          [NAS]                        [新機器 / CI]
  bin\installers\*               ssd-testkit-source\
  bin\chocolatey\packages\*        windows\zip\*.zip  ◄──────  prepare_testcase.bat
        │                          windows\nupkg\               解壓到 bin\installers\
        │  upload_tools_to_nexus.bat
        ▼
  [Nexus: choco-hosted-nas]  ◄──────────────────────────────  prepare_testcase.bat
  https://10.252.170.171                                         下載 .nupkg
```

---

## 重要路徑

| 位置 | 說明 |
|------|------|
| `bin\installers\<ToolName>\<version>\` | 廠商原始安裝檔（git-ignored，不 commit） |
| `bin\chocolatey\packages\<id>\<version>\<id>.<version>.nupkg` | Chocolatey 套件（薄包裝腳本，無 binary） |
| `lib\testtool\tools-registry.yaml` | 所有工具的版本、路徑集中設定 |
| `tool-manager\prepare.yaml` | 目前要準備的 testcase 名稱 |
| `tests\integration\test_case\<name>\Config\tools.yaml` | 此 testcase 需要的工具 id 清單 |

### NAS 路徑
| 路徑 | 說明 |
|------|------|
| `\\10.250.0.1\mdt\Team\PQ1-3\tool\ssd-testkit-source\windows\zip\` | installer zip 靜態備份（prepare_testcase 下載來源） |
| `\\10.250.0.1\mdt\Team\PQ1-3\tool\ssd-testkit-source\windows\nupkg\` | .nupkg 靜態備份 |
| `\\10.250.0.1\mdt\Team\PQ1-3\tool\ssd-testkit-nexus\` | Nexus blob store 實體位置（不手動動） |
| NAS 認證 | user: `mdt` / pass: `p@ssw0rd` |

### Nexus
| 項目 | 值 |
|------|---|
| URL | `https://10.252.170.171` |
| Repository | `choco-hosted-nas`（NuGet 格式） |
| 帳號 | `admin` / `1.a` |
| 注意 | Windows 需加 `--ssl-no-revoke --noproxy 10.252.170.171` 才能連通 |

---

## tools-registry.yaml 欄位

位於 `lib\testtool\tools-registry.yaml`：

```yaml
tools:
  smicli:
    version:     2026.2.13          # Nexus nupkg 版本號（必填）
    source_dir:  bin/installers/SmiCli/v20260213C   # 本機 installer 相對路徑
    nexus_path:  windows-tools/SmiCli/v20260213C/SmiCli-v20260213C.zip  # NAS zip 檔名依據
    install_dir: C:\tools\SmiCli    # 安裝後位置（偵測是否已安裝用）
    env_var:     SMICLI_PATH
    binaries:    [SmiCli2.exe]      # 第一個 binary 用來偵測是否已安裝

  windows-adk:
    version:     26100.0.0
    install_dir: C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit
    binaries:    [wpr.exe, wpa.exe, xbootmgr.exe]
    # 沒有 source_dir / nexus_path → 不做 installer zip 備份
```

`nexus_path` 最後一段即為 NAS zip 檔名：`SmiCli-v20260213C.zip`

---

## 工具一覽

| id | 版本 | source_dir | 說明 |
|----|------|------------|------|
| `smicli` | 2026.2.13 | `bin/installers/SmiCli/v20260213C` | SMI CLI |
| `smiwintools` | 2026.2.13.1 | `bin/installers/SmiWinTools/v20260213C` | SMI WinTools |
| `burnin` | 10.2.1004 | `bin/installers/BurnIn/10.2.1004` | BurnInTest |
| `cdi` | 8.17.13 | `bin/installers/CrystalDiskInfo/8.17.13` | CrystalDiskInfo |
| `phm` | 4.22.0 | `bin/installers/PHM/V4.22.0_B25.02.06.02_H` | PowerhouseMountain |
| `windows-adk` | 26100.0.0 | (無) | Windows ADK，需另外安裝 |

---

## 腳本說明

### prepare_testcase.bat / .ps1

**用途**：在新機器上準備 testcase 所需工具。

**執行方式**：
```powershell
# 使用 prepare.yaml 指定的 testcase
.\tool-manager\prepare_testcase.bat

# 一次性指定 testcase
.\tool-manager\prepare_testcase.ps1 stc1685_burnin
```

**三個步驟**：
1. **Step 1**：`.nupkg` 不存在 → 從 Nexus `choco-hosted-nas` 下載至 `bin\chocolatey\packages\`
2. **Step 1.5**：`bin\installers\<source_dir>\` 不存在 → 從 NAS `windows\zip\` 複製 zip 解壓
3. NAS 自動掛載（session 不保留，腳本開頭自動 `net use`）

**輸出範例**：
```
TestCase: stc1685_burnin
  [NAS] Connecting to \\10.250.0.1\mdt ...
  [DOWNLOAD] smicli 2026.2.13          ← 從 Nexus 下載 nupkg
  [COPY] installer smicli  \\...\zip\SmiCli-v20260213C.zip  ← 從 NAS 解壓
  [SKIP] installer cdi (bin\installers already present)
Tools ready: stc1685_burnin
```

---

### upload_tools_to_nexus.bat / .ps1

**用途**：在有完整 `bin\` 的機器上，把工具備份到 Nexus 和 NAS（新增工具或升版時執行一次）。

**執行方式**：
```powershell
.\tool-manager\upload_tools_to_nexus.bat
```

**兩個部分**：
- **Part 1**：`bin\chocolatey\packages\<id>\<version>\*.nupkg` → POST 到 Nexus `choco-hosted-nas`
  - 缺 `.nupkg` 時自動 `choco pack` 從 nuspec 建立
  - 已存在則顯示 `[EXISTS]` 跳過
- **Part 2**：`bin\installers\<source_dir>\*` → `Compress-Archive` → Copy 到 NAS `windows\zip\`
  - 已存在則顯示 `[EXISTS]` 跳過

**curl 注意事項**（Windows 特有）：
```powershell
# 必須加這兩個參數，否則 HTTPS 憑證失敗或走 proxy timeout
curl.exe -sk --ssl-no-revoke --noproxy "10.252.170.171" -u "admin:1.a" ...

# URL 必須放在 -F 之後，且不能加 -X POST（由 -F 自動推斷）
curl.exe ... -F "nuget.asset=@file.nupkg" $uploadUrl
```

---

## 新增工具完整流程

以新增 `smicli v20260401A`（Chocolatey 版本 `2026.4.1`）為例：

### Step A：放入 installer 檔案
```
bin\installers\SmiCli\v20260401A\
    SmiCli2.exe
    SmiCli2.pdb
    WinIo64.sys
```

### Step B：建立 / 更新 Chocolatey 套件定義
複製現有版本：
```
bin\chocolatey\packages\smicli\
└── 2026.4.1\          ← 新建，複製自 2026.2.13\
    ├── smicli.nuspec
    └── tools\
        ├── chocolateyInstall.ps1    ← 改 $toolVersion = "v20260401A"
        └── chocolateyUninstall.ps1
```

修改 `smicli.nuspec`：
```xml
<version>2026.4.1</version>
```

修改 `chocolateyInstall.ps1`（只改一行）：
```powershell
$toolVersion = "v20260401A"
```

### Step C：更新 tools-registry.yaml
```yaml
smicli:
  version:    2026.4.1
  source_dir: bin/installers/SmiCli/v20260401A
  nexus_path: windows-tools/SmiCli/v20260401A/SmiCli-v20260401A.zip
  install_dir: C:\\tools\\SmiCli
  binaries:   [SmiCli2.exe]
```

### Step D：上傳到 Nexus + NAS
```powershell
.\tool-manager\upload_tools_to_nexus.bat
# → [PACK]   smicli 2026.4.1       (自動 choco pack)
# → [UPLOAD] smicli 2026.4.1  HTTP 204
# → [ZIP]    smicli  bin\installers\SmiCli\v20260401A
# → [COPY]   smicli  → NAS\zip\SmiCli-v20260401A.zip
```

### Step E：驗證其他機器可下載
```powershell
# 刪除本地快取模擬新機器
Remove-Item bin\chocolatey\packages\smicli\2026.4.1\ -Recurse -Force
Remove-Item bin\installers\SmiCli\v20260401A\ -Recurse -Force

.\tool-manager\prepare_testcase.bat
# → [DOWNLOAD] smicli 2026.4.1
# → [COPY] installer smicli  \\...\zip\SmiCli-v20260401A.zip
```

---

## 常見問題排查

| 症狀 | 原因 | 解法 |
|------|------|------|
| `zip not found on NAS` | NAS zip 尚未上傳 | 在有 `bin\installers\` 的機器執行 `upload_tools_to_nexus.bat` |
| `nupkg download failed (curl exit 56)` | Nexus 上沒有此工具的 nupkg | 執行 `upload_tools_to_nexus.bat` 上傳 nupkg |
| `HTTP 000` nupkg 上傳失敗 | curl schannel 憑證問題或走 proxy | 確認 `--ssl-no-revoke --noproxy 10.252.170.171` 有加，且 URL 放 `-F` 之後 |
| NAS `[WARN] Failed to connect` | NAS session 未掛載 | 腳本自動執行 `net use`，若失敗確認網路連到 `10.250.0.1` |
| `Installer not found: bin\installers\...` | `chocolateyInstall.ps1` 找不到安裝檔 | Step 1.5 確保 installer 下載後再執行 `choco install` |
