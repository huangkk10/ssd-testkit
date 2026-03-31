# tool-manager

在跑測試前，把 test case 所需的工具準備好。

- **`prepare_testcase`**：下載 `.nupkg`（Nexus）及 installer 檔（NAS），確保工具就位
- **`upload_tools_to_nexus`**：上傳 `.nupkg` 到 Nexus，並將 `bin\installers\` 的 zip 備份到 NAS

---

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `prepare.yaml` | 指定目前要準備的 test case 名稱 |
| `prepare_testcase.ps1` | 主腳本：下載 `.nupkg` + installer zip 到本機 |
| `prepare_testcase.bat` | 一鍵執行 prepare_testcase.ps1（雙擊即可） |
| `upload_tools_to_nexus.ps1` | 上傳 `.nupkg` 到 Nexus；zip `bin\installers\` 並複製到 NAS |
| `upload_tools_to_nexus.bat` | 一鍵執行 upload_tools_to_nexus.ps1（雙擊即可） |

---

## 運作原理

```
prepare_testcase.ps1
  │
  ├─ 讀 prepare.yaml (或命令列參數) → 得到 testcase 名稱
  │
  ├─ 讀 tests/integration/test_case/<testcase>/Config/tools.yaml
  │    → 得到這個 test case 需要哪些工具 (id 清單)
  │
  ├─ 讀 lib/testtool/tools-registry.yaml
  │    → 得到每個工具的 version / source_dir / nexus_path / install_dir
  │
  └─ 對每個工具：
       ├─ Step 1  : .nupkg 不存在 → 從 Nexus choco-hosted 下載
       │            .nupkg 已存在 → [SKIP]
       │
       └─ Step 1.5: bin\installers\<source_dir>\ 不存在
                     → 從 NAS ssd-testkit-source\windows\zip\ 複製 zip 並解壓
                    bin\installers\<source_dir>\ 已存在 → [SKIP]


upload_tools_to_nexus.ps1
  │
  ├─ Part 1: 上傳 .nupkg → Nexus choco-hosted
  │    ├─ .nupkg 存在    → POST 上傳
  │    ├─ .nupkg 不存在  → choco pack 後上傳
  │    └─ 已在 Nexus 上  → [EXISTS] 跳過
  │
  └─ Part 2: 備份 installer zip → NAS
       ├─ bin\installers\<source_dir>\ 存在 → Compress-Archive → COPY 到 NAS
       └─ NAS 上已有同名 zip               → [EXISTS] 跳過
```

---

## 使用說明

### 1. 日常使用：準備工具

**步驟一**：編輯 `prepare.yaml`，填入要準備的 test case 名稱：

```yaml
testcase: stc1685_burnin
```

**步驟二**：雙擊 `prepare_testcase.bat`，或在命令列執行：

```
prepare_testcase.bat
```

**輸出範例（工具已存在時）：**
```
TestCase: stc1685_burnin
  [SKIP] smicli 2026.2.13
  [SKIP] installer smicli (bin\installers already present)
Tools ready: stc1685_burnin
```

**輸出範例（需要下載時）：**
```
TestCase: stc1685_burnin
  [DOWNLOAD] smicli 2026.2.13
  [COPY] installer smicli  \\10.250.0.1\...\zip\SmiCli-v20260213C.zip
Tools ready: stc1685_burnin
```

---

### 2. 切換 test case

修改 `prepare.yaml` 再執行，或直接帶參數：

```
prepare_testcase.bat stc2562
```

---

### 3. 上傳工具到 Nexus + NAS（新增或更新工具版本時）

在有完整 `bin\installers\` 和 `bin\chocolatey\packages\` 的機器上執行：

```
upload_tools_to_nexus.bat
```

腳本會：
1. 把 `.nupkg` POST 到 Nexus `choco-hosted`（已存在則跳過）
2. 把 `bin\installers\<source_dir>\*` zip 後複製到 NAS `ssd-testkit-source\windows\zip\`（已存在則跳過）

---

## 設定檔說明

### prepare.yaml

```yaml
testcase: stc1685_burnin
```

### tools.yaml（各 test case 專屬）

位於 `tests/integration/test_case/<name>/Config/tools.yaml`：

```yaml
tools:
  - id: smicli
  - id: burnin
  - id: cdi
```

### tools-registry.yaml（工具中央登錄）

位於 `lib/testtool/tools-registry.yaml`：

```yaml
tools:
  smicli:
    version:     2026.2.13
    source_dir:  bin/installers/SmiCli/v20260213C      # 本機 installer 路徑
    nexus_path:  windows-tools/SmiCli/v20260213C/SmiCli-v20260213C.zip  # zip 檔名依據
    install_dir: C:\tools\SmiCli                        # 已安裝位置（偵測用）
    binaries:    [SmiCli2.exe]
```

- 沒有 `source_dir` 的工具（如 `windows-adk`）Step 1.5 會自動略過
- `nexus_path` 的最後一段（`SmiCli-v20260213C.zip`）即為 NAS 上的 zip 檔名

---

## 目前支援的工具 id

| id | 版本 | 說明 |
|----|------|------|
| `smicli` | 2026.2.13 | SMI CLI 工具 |
| `smiwintools` | 2026.2.13.1 | SMI Windows 工具集 |
| `burnin` | 10.2.1004 | BurnInTest |
| `cdi` | 8.17.13 | CrystalDiskInfo |
| `phm` | 4.22.0 | PowerhouseMountain |
| `windows-adk` | 26100.0.0 | Windows ADK (wpr/wpa/xbootmgr)，無 installer zip |

---

## NAS 路徑參考

```
\\10.250.0.1\mdt\Team\PQ1-3\tool\
├── ssd-testkit-nexus/        ← Nexus blob store（.nupkg 實體存放）
├── ssd-testkit-backup/       ← nexus-data 每日快照（保留 14 天）
└── ssd-testkit-source/
    └── windows/
        ├── installers/       ← 原始安裝資料夾
        ├── zip/              ← installer zip（prepare_testcase 下載來源）
        └── nupkg/            ← .nupkg 靜態備份
```
