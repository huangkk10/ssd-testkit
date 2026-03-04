# CDI (CrystalDiskInfo) — Tool Reference

> Status: SCAFFOLD COMPLETE — Migrated from legacy `lib/testtool/CDI.py`

---

## 1. 工具概覽

**CrystalDiskInfo (CDI)** 是 Windows 硬碟健康狀態監控工具，透過 SMART 資料讀取 SSD 健康度。

| 項目 | 值 |
|------|----|
| 用途 | 自動匯出 SMART 文字報告、解析成 JSON、截取磁碟截圖；測試前後 SMART 值比對 |
| 執行類型 | GUI（`DiskInfo64.exe`，pywinauto 自動化） |
| 需要安裝 | ❌ 直接放 bin/ 目錄即可 |
| 有 GUI | ✅ pywinauto（`win32` backend） |
| 需產生腳本 | ❌ |
| 結果解析 | `log_file`（`DiskInfo.txt` → JSON） |
| 遺留檔案 | `lib/testtool/CDI.py` — **已標記 deprecated**，勿使用 |

---

## 2. 執行檔位置

```
./bin/CrystalDiskInfo/DiskInfo64.exe
```

> 預設相對路徑。可透過 `executable_path` 設定覆蓋。

---

## 3. 套件結構

```
lib/testtool/cdi/
├── __init__.py       # exports CDIController, CDIConfig, CDIUIMonitor, exceptions
├── config.py         # CDIConfig, DEFAULT_CONFIG, validate_config(), merge_config()
├── controller.py     # CDIController(threading.Thread) + CDILogParser
├── exceptions.py     # 例外階層
└── ui_monitor.py     # pywinauto UI 自動化（開啟、截圖、儲存、關閉）
```

> ⚠️ `CDILogParser` 定義在 `controller.py` 中（非獨立 `log_parser.py`），同時從 `__init__.py` 匯出。

---

## 4. 例外階層（`exceptions.py`）

```python
class CDIError(Exception)
class CDIConfigError(CDIError)
class CDITimeoutError(CDIError)
class CDIProcessError(CDIError)
class CDIUIError(CDIError)
class CDITestFailedError(CDIError)
```

---

## 5. 設定參數（`CDIConfig.DEFAULT_CONFIG`）

| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `executable_path` | `str` | `./bin/CrystalDiskInfo/DiskInfo64.exe` | DiskInfo64.exe 路徑 |
| `log_path` | `str` | `./testlog` | log 輸出目錄 |
| `log_prefix` | `str` | `""` | 所有輸出檔名前綴 |
| `screenshot_drive_letter` | `str` | `""` | 截圖磁碟代號（如 `C:`）；空=全部 |
| `diskinfo_txt_name` | `str` | `DiskInfo.txt` | 文字報告檔名 |
| `diskinfo_json_name` | `str` | `DiskInfo.json` | 解析後 JSON 檔名 |
| `diskinfo_png_name` | `str` | `""` | 截圖檔名 |
| `window_title` | `str` | `" CrystalDiskInfo "` | pywinauto 視窗標題 |
| `window_class` | `str` | `"#32770"` | pywinauto 視窗類別 |
| `save_dialog_timeout` | `int/float` | `20` | 儲存對話框等待秒數 |
| `save_retry_max` | `int` | `10` | 儲存重試次數上限 |
| `timeout_seconds` | `int` | `300` | 整體執行 timeout（秒） |
| `check_interval_seconds` | `float` | `2.0` | 狀態輪詢間隔（秒） |

---

## 6. Controller 工作流程

```
CDIController.run()
├── kill stale DiskInfo64.exe process（避免殘留）
├── open UI（pywinauto Application.start()）
├── export text log（File → Save → DiskInfo.txt）
├── CDILogParser.parse_file() → DiskInfo.json
├── capture screenshot（per drive）
└── close UI
```

公開 API：
- `status: Optional[bool]` — `None`（執行中）/ `True`（Pass）/ `False`（Fail）
- `compare_smart_value_no_increase(drive, prefix_before, prefix_after, attributes)` — 比對兩次 SMART 快照，驗證指定屬性值未增加

---

## 7. `CDILogParser` — SMART 解析

`CDILogParser.parse_file(txt_path, json_output_path=None)` 將 `DiskInfo.txt` 解析成：

```python
{
    "cdi_version": "...",
    "disks": [
        {
            "Model": "Samsung SSD 980 PRO 1TB",
            "Drive Letter": "C:",
            "Health Status": "Good",
            "smart": {
                "05": {"name": "Reallocated Sectors Count", "current": 100, "raw": 0},
                ...
            }
        }
    ]
}
```

狀態機模式（`ReadMode` enum）：`start → cdiversion → controllermap → disklist → drivedata → smartdata → ...`

---

## 8. 使用範例

### 基本快照（單次）

```python
from lib.testtool.cdi import CDIController

controller = CDIController(
    executable_path='./bin/CrystalDiskInfo/DiskInfo64.exe',
    log_path='./testlog',
    log_prefix='Before_',
    screenshot_drive_letter='C:',
)
controller.start()
controller.join(timeout=300)

assert controller.status is True, 'CDI workflow FAILED'
```

### 測試前後 SMART 比對

```python
# 測試前快照
before = CDIController(log_path='./testlog', log_prefix='Before_')
before.start(); before.join(timeout=300)

# ... 執行測試 ...

# 測試後快照
after = CDIController(log_path='./testlog', log_prefix='After_')
after.start(); after.join(timeout=300)

# 比對 SMART 值（指定屬性不應增加）
ok, msg = after.compare_smart_value_no_increase(
    'C:', 'Before_', 'After_',
    ['Unsafe Shutdowns', 'Power Cycles', 'Media and Data Integrity Errors']
)
assert ok, msg
```

---

## 9. 遺留檔案說明

`lib/testtool/CDI.py` 保留為向下相容，但已加上 `DeprecationWarning`：
```
lib.testtool.CDI is deprecated and will be removed in a future release.
Use 'from lib.testtool.cdi import CDIController' instead.
```

---

## 10. 相關路徑

| 資源 | 路徑 |
|------|------|
| 套件程式碼 | `lib/testtool/cdi/` |
| 遺留檔案（deprecated） | `lib/testtool/CDI.py` |
| 執行檔 | `./bin/CrystalDiskInfo/DiskInfo64.exe` |
