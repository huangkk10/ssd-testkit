# tool-manager

在跑測試前，把 test case 所需的 bin 工具準備好。
工具來源優先從 `bin/installers/` 本機複製，若不存在則從 Nexus 下載。

---

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `prepare.yaml` | 指定目前要準備的 test case 名稱 |
| `prepare_testcase.ps1` | 主腳本：把 test case 需要的工具複製到其 `bin/` |
| `prepare_testcase.bat` | 一鍵執行 prepare_testcase.ps1（雙擊即可） |
| `upload_tools_to_nexus.ps1` | 將 `bin/installers/` 下的工具 zip 並上傳到 Nexus |
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
  │    → 得到每個工具的 bin_dir / source_dir / nexus_path
  │
  └─ 對每個工具：
       ├─ 若 bin/<bin_dir>/ 已存在 → [SKIP]
       ├─ 若 bin/installers/<source_dir>/ 存在 → [COPY] 本機複製
       └─ 否則 → [DOWNLOAD] 從 Nexus 下載 zip 並解壓
```

---

## 快速使用

### 1. 日常使用：準備 bin 工具

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
  [SKIP] smicli already exists
  [SKIP] burnin already exists
bin/ ready: stc1685_burnin
```

**輸出範例（工具不存在，從本機複製）：**
```
TestCase: stc1685_burnin
  [COPY] smicli  C:\ssd-testkit\bin\installers\SmiCli\v20260213C -> ...\bin\SmiCli
  [COPY] burnin  C:\ssd-testkit\bin\installers\BurnIn\10.2.1004  -> ...\bin\BurnIn
bin/ ready: stc1685_burnin
```

---

### 2. 切換 test case

只需修改 `prepare.yaml` 的 testcase 值，再執行一次 bat：

```yaml
testcase: stc2562
```

或不改 yaml，直接帶參數執行（一次性覆蓋）：

```
prepare_testcase.bat stc2562
```

---

### 3. 工具版本更新後強制重新複製

加上 `-Force` 旗標，即使目錄已存在也會重新複製：

```
prepare_testcase.bat -Force
```

---

### 4. 上傳工具到 Nexus（版本更新時）

當 `bin/installers/` 有新版工具，需要更新 Nexus 備援來源時執行：

```
upload_tools_to_nexus.bat
```

腳本會自動讀 `lib/testtool/tools-registry.yaml`，把所有有 `source_dir` + `nexus_path` 的工具打成 zip 並 PUT 到 Nexus `raw-windows-tools` repo。

---

## 設定檔說明

### prepare.yaml

位於 `tool-manager/prepare.yaml`，指定預設 test case：

```yaml
testcase: stc1685_burnin
```

### tools.yaml（各 test case 專屬）

位於 `tests/integration/test_case/<name>/Config/tools.yaml`，
列出這個 test case 需要的工具 id：

```yaml
tools:
  - id: smicli
    phase: pre_runcard   # 選填，供測試框架判斷執行階段
  - id: smiwintools
    phase: pre_runcard
  - id: burnin
  - id: cdi
```

### tools-registry.yaml（工具中央登錄）

位於 `lib/testtool/tools-registry.yaml`，集中定義所有工具屬性：

```yaml
tools:
  smicli:
    bin_dir:    SmiCli                                # 複製到 bin/<bin_dir>/
    source_dir: bin/installers/SmiCli/v20260213C      # 本機來源
    nexus_path: windows-tools/SmiCli/v20260213C/SmiCli-v20260213C.zip  # Nexus 備援
    install_dir: C:\tools\SmiCli
    env_var:    SMICLI_PATH
    binaries:   [SmiCli2.exe]
```

若某工具沒有 `bin_dir`（如 `windows-adk`），prepare 腳本會自動略過，不影響安裝流程。

---

## 目前支援的工具 id

| id | bin_dir | 說明 |
|----|---------|------|
| `smicli` | SmiCli | SMI CLI 工具 |
| `smiwintools` | SmiWinTools | SMI Windows 工具集 |
| `burnin` | BurnIn | BurnInTest |
| `cdi` | CrystalDiskInfo | 磁碟資訊工具 |
| `phm` | PHM | PowerhouseMountain |
| `windows-adk` | (無，已安裝) | Windows ADK (wpr/wpa/xbootmgr) |
