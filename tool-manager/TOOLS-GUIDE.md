# Tool Manager 使用指南

管理測試工具的打包、上傳至 Nexus、本地下載與安裝流程。

---

## 目錄結構

```
C:\ssd-testkit\
├── tool-manager\
│   ├── TOOLS-GUIDE.md              ← 本文件
│   ├── prepare_testcase.ps1        ← 安裝 test case 所需工具
│   ├── prepare_testcase.bat
│   ├── upload_tools_to_nexus.ps1   ← 上傳 .nupkg 到 Nexus
│   ├── upload_tools_to_nexus.bat
│   └── prepare.yaml                ← 預設 testcase 名稱設定
│
├── lib\testtool\
│   └── tools-registry.yaml         ← 所有工具的版本/路徑集中設定
│
├── bin\chocolatey\packages\
│   └── <tool-id>\
│       ├── <tool-id>.nuspec        ← 套件描述 (choco pack 來源)
│       ├── tools\
│       │   ├── chocolateyInstall.ps1
│       │   └── chocolateyUninstall.ps1
│       └── <version>\
│           └── <tool-id>.<version>.nupkg   ← 已打包的套件
│
└── tests\integration\test_case\
    └── <testcase-name>\
        └── Config\
            └── tools.yaml          ← 此 test case 需要哪些工具
```

---

## Nexus 資訊

| 項目 | 值 |
|------|----|
| URL  | https://nexus.internal |
| Repo | `choco-hosted` (NuGet 格式) |
| 帳號 | admin / 1.a |

---

## 1. 打包 .nupkg（choco pack）

適用情境：新增工具或更新版本時，從 nuspec 建立 .nupkg。

**前提：**
- `bin\chocolatey\packages\<id>\<id>.nuspec` 已存在
- `bin\chocolatey\packages\<id>\tools\chocolateyInstall.ps1` 已存在

**指令：**

```powershell
cd C:\ssd-testkit
choco pack bin\chocolatey\packages\smicli\smicli.nuspec `
    --outputdirectory bin\chocolatey\packages\smicli\2026.2.13 `
    --version 2026.2.13
```

或直接執行上傳腳本（自動 pack 缺少的 nupkg）：

```powershell
.\tool-manager\upload_tools_to_nexus.ps1
```

---

## 2. 上傳 .nupkg 到 Nexus

腳本會讀取 `lib\testtool\tools-registry.yaml`，對每個有 `version` 欄位的工具：
1. 確認 `bin\chocolatey\packages\<id>\<version>\<id>.<version>.nupkg` 存在
2. 若不存在，嘗試 `choco pack` 自動建立
3. 上傳至 `choco-hosted` repo

```powershell
cd C:\ssd-testkit

# 使用預設帳號 admin/1.a
.\tool-manager\upload_tools_to_nexus.bat

# 指定不同帳號
.\tool-manager\upload_tools_to_nexus.ps1 -NexusUser uploader -NexusPass "Uploader@2026"
```

**上傳輸出範例：**
```
  [UPLOAD] smicli 2026.2.13  (12.5 MB)
  [OK]     smicli  HTTP 204
  [EXISTS] windows-adk (already in choco-hosted, skipped)
```

**手動 curl 上傳（單一檔案）：**

```powershell
curl.exe -sk -u "admin:1.a" `
  -X POST "https://nexus.internal/service/rest/v1/components?repository=choco-hosted" `
  -F "nuget.asset=@C:\ssd-testkit\bin\chocolatey\packages\smicli\2026.2.13\smicli.2026.2.13.nupkg"
```

---

## 3. 下載 .nupkg 到本地

從 Nexus 下載 .nupkg 到 `bin\chocolatey\packages\` 快取，供離線 / 打包成 .exe 用。

**透過 prepare_testcase.ps1 自動下載（推薦）：**

```powershell
.\tool-manager\prepare_testcase.bat
# 或指定 testcase
.\tool-manager\prepare_testcase.ps1 stc1685_burnin
```

腳本會對每個工具先下載 .nupkg（若本地沒有），再判斷是否需要安裝。

**手動下載單一套件：**

```powershell
# URL 格式：https://nexus.internal/repository/choco-hosted/<id>/<version>
$headers = @{ Authorization = "Basic " + [Convert]::ToBase64String(
    [Text.Encoding]::ASCII.GetBytes("admin:1.a")) }

Invoke-WebRequest `
  -Uri "https://nexus.internal/repository/choco-hosted/smicli/2026.2.13" `
  -Headers $headers `
  -OutFile "C:\ssd-testkit\bin\chocolatey\packages\smicli\2026.2.13\smicli.2026.2.13.nupkg"
```

---

## 4. 安裝工具（choco install）

### 方式 A：從本地快取安裝（推薦，離線可用）

```powershell
choco install smicli `
  --source "C:\ssd-testkit\bin\chocolatey\packages\smicli\2026.2.13" `
  -y --no-progress
```

### 方式 B：直接從 Nexus 安裝（需連網）

```powershell
choco install smicli `
  --source "https://nexus.internal/repository/choco-hosted" `
  --version 2026.2.13 `
  -y --no-progress
```

### 方式 C：透過 prepare_testcase 自動安裝（推薦用於 test case）

```powershell
cd C:\ssd-testkit

# 安裝 prepare.yaml 中指定的 testcase 所需工具
.\tool-manager\prepare_testcase.bat

# 指定 testcase
.\tool-manager\prepare_testcase.ps1 stc2557_adk_s3s4s5

# 強制重新安裝（即使已安裝）
.\tool-manager\prepare_testcase.ps1 stc2557_adk_s3s4s5 -Force
```

**輸出範例：**
```
TestCase: stc2557_adk_s3s4s5
  [DOWNLOAD] smicli 2026.2.13
  [SKIP] smicli (C:\tools\SmiCli\SmiCli2.exe)
  [DOWNLOAD] windows-adk 26100.0.0
  [SKIP] windows-adk (C:\...\wpr.exe)
Tools ready: stc2557_adk_s3s4s5
```

---

## 5. 查詢 Nexus 已上傳的套件

```powershell
# 列出 choco-hosted 所有套件
curl.exe -sk -u "admin:1.a" `
  "https://nexus.internal/service/rest/v1/components?repository=choco-hosted" | `
  python -c "import sys,json; [print(c['name'], c['version']) for c in json.load(sys.stdin)['items']]"
```

---

## 6. tools-registry.yaml 欄位說明

```yaml
tools:
  smicli:
    version: 2026.2.13            # Nexus 上的套件版本（必填）
    install_dir: C:\\tools\\SmiCli  # 安裝後的目錄（用於偵測是否已安裝）
    binaries: [SmiCli2.exe]       # 偵測已安裝的目標執行檔（在 install_dir 底下）
    env_var: SMICLI_PATH          # 環境變數名稱（選填）
```

> 若 `binaries` 為空，prepare_testcase 改以 `install_dir` 是否存在作為判斷依據。

---

## 流程總覽

```
nuspec + chocolateyInstall.ps1
        │
        ▼ choco pack
   <id>.<version>.nupkg  (bin\chocolatey\packages\<id>\<version>\)
        │
        ▼ upload_tools_to_nexus.ps1
   Nexus choco-hosted
        │
        ▼ prepare_testcase.ps1 Step 1
   bin\chocolatey\packages\<id>\<version>\ (本地快取)
        │
        ▼ prepare_testcase.ps1 Step 2-3
   choco install → 工具安裝至 C:\tools\ 或 C:\Program Files\
```
