# SleepStudy — Tool Reference

> Migrated from: `lib/testtool/phm/sleep_report_parser.py` (PHM shim still active for backward-compat)
> Ticket: STC-2562 (split-out)
> Status: COMPLETE — all 98 unit tests + integration tests passing

---

## 1. 工具概覽

**SleepStudy** 是 Windows 內建 `powercfg /sleepstudy` 的獨立 testtool wrapper。

| 項目 | 值 |
|------|----|
| 用途 | 執行 `powercfg /sleepstudy /output <path>` 產生 HTML 報告，並解析 Sleep Session 資料 |
| 命令 | `powercfg /sleepstudy /output <output_path>` |
| 結果格式 | HTML（內嵌 `LocalSprData` JSON 物件） |
| 架構 | `SleepStudyController(threading.Thread)` + `SleepReportParser` + `SleepStudyConfig` |
| 來源 | 由 `lib.testtool.phm.sleep_report_parser` 遷移而來 |

---

## 2. 套件結構

```
lib/testtool/sleepstudy/
├── __init__.py              # 套件入口、exports
├── config.py                # DEFAULT_CONFIG、SleepStudyConfig、merge_config()
├── controller.py            # 主控制器（繼承 threading.Thread）
├── exceptions.py            # 例外階層
├── history_cleaner.py       # 清除系統 SleepStudy 歷史記錄（SleepHistoryCleaner）
└── sleep_report_parser.py   # HTML 報告解析（SleepReportParser、SleepSession）
```

> ⚠️ `lib/testtool/phm/sleep_report_parser.py` 已改為 re-export shim（向下相容）。  
> ⚠️ 新程式碼請直接 import `lib.testtool.sleepstudy`。

---

## 3. 例外階層（`exceptions.py`）

```python
class SleepStudyError(Exception)              # 根例外
class SleepStudyConfigError(SleepStudyError)  # 設定錯誤
class SleepStudyTimeoutError(SleepStudyError) # 超時
class SleepStudyProcessError(SleepStudyError) # powercfg 執行失敗
class SleepStudyLogParseError(SleepStudyError)# HTML 報告解析失敗
class SleepStudyTestFailedError(SleepStudyError)# 測試結果 FAIL
class SleepStudyClearError(SleepStudyError)   # 歷史記錄清除失敗（PermissionError / OSError）
```

**Backward-compat alias（`lib.testtool.phm.exceptions`）：**
```python
PHMSleepReportParseError = SleepStudyLogParseError  # alias
```

---

## 4. 設定參數（`config.py` DEFAULT_CONFIG）

| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `output_path` | `str` | `"sleepstudy-report.html"` | HTML 報告輸出路徑 |
| `timeout` | `int` | `60` | powercfg 執行超時秒數 |

```python
from lib.testtool.sleepstudy.config import SleepStudyConfig, merge_config

config = SleepStudyConfig.get_default_config()
config.update({"output_path": "./testlog/sleepstudy.html", "timeout": 120})
```

---

## 5. Controller API（`controller.py`）

```python
from lib.testtool.sleepstudy import SleepStudyController, SleepStudyConfig

config = SleepStudyConfig.get_default_config()
config.update({"output_path": "./testlog/sleepstudy.html"})

controller = SleepStudyController(**config)
controller.start()
controller.join(timeout=120)

# 取得 parser
parser = controller.get_parser()
sessions = parser.get_sleep_sessions(start_dt="2026-03-04")
```

**`SleepStudyController` 關鍵屬性：**

| 成員 | 型別 | 說明 |
|------|------|------|
| `status` | `bool\|None` | `None`=執行中，`True`=成功，`False`=失敗 |
| `output_path` | `Path` | resolved 輸出路徑 |
| `get_parser()` | `SleepReportParser` | 取得解析器（若報告不存在拋 `SleepStudyProcessError`）|

**`run()` 執行流程：**
```
SleepStudyController.run()
  └─ subprocess.run(["powercfg", "/sleepstudy", "/output", str(output_path)])
     ├─ returncode != 0 → raise SleepStudyProcessError
     └─ output file missing → raise SleepStudyProcessError
```

---

## 6. History Cleaner API（`history_cleaner.py`）

在執行 `powercfg /sleepstudy` 前，先清除系統積累的歷史記錄，確保報告只包含本次測試週期資料。

**目標路徑（清除直接子檔案，不刪除目錄本身）：**

| 常數 | 路徑 |
|------|------|
| `SLEEP_STUDY_DIR` | `C:\Windows\System32\SleepStudy\` |
| `SLEEP_STUDY_SCREENON_DIR` | `C:\Windows\System32\SleepStudy\ScreenOn\` |

> ⚠️ 需要 Administrator 權限。

### import

```python
from lib.testtool.sleepstudy import SleepHistoryCleaner, SleepStudyClearError
```

### 基本用法

```python
cleaner = SleepHistoryCleaner()
del_count = cleaner.clear()          # raise_on_error=True（預設，遇錯立即拋）
print(f"Deleted {del_count} files")
print(f"Skipped (not found): {cleaner.skipped_dirs}")
```

### 容錯模式

```python
cleaner = SleepHistoryCleaner()
cleaner.clear(raise_on_error=False)  # 收集錯誤，不中止
if cleaner.errors:
    for file_path, exc in cleaner.errors:
        print(f"  FAILED: {file_path}: {exc}")
```

### 自訂目標路徑（測試用）

```python
cleaner = SleepHistoryCleaner(target_dirs=["C:/tmp/FakeSleepStudy"])
cleaner.clear()
```

### `SleepHistoryCleaner` 屬性

| 屬性 | 型別 | 說明 |
|------|------|------|
| `deleted_files` | `list[Path]` | 本次 `clear()` 成功刪除的檔案 |
| `skipped_dirs` | `list[Path]` | 目錄不存在而跳過的路徑 |
| `errors` | `list[tuple[Path, Exception]]` | `raise_on_error=False` 時收集的 `(file, exc)` |

### 典型測試流程（搭配 Controller）

```python
from lib.testtool.sleepstudy import SleepHistoryCleaner, SleepStudyController

# Step 1: 清除舊記錄
SleepHistoryCleaner().clear()

# Step 2: 執行測試（讓 DUT 進入 Sleep）
# ... 測試邏輯 ...

# Step 3: 產生報告並解析
ctrl = SleepStudyController(output_path="./testlog/sleepstudy.html")
ctrl.start()
ctrl.join()
parser = ctrl.get_parser()
sessions = parser.get_sleep_sessions(start_dt="2026-03-05")
```

### 行為細節
- 掃描每個目錄的**直接子檔案**（`Path.is_file()`），不遞迴
- 掃描 `SleepStudy\` 時遇到 `ScreenOn` 子目錄，自動跳過（`is_file()` 過濾）
- 每次呼叫 `clear()` 都重置 `deleted_files` / `skipped_dirs` / `errors`

---

## 7. 解析器 API（`sleep_report_parser.py`）

Windows `powercfg /sleepstudy` 產生的 HTML 報告解析模組。  
報告內嵌 `LocalSprData` JSON，包含所有 Session 資料。

### 解析策略
1. **Regex（主路徑）**：`LocalSprData` 是靜態 JSON literal，regex 快速提取，零延遲。
2. **Playwright fallback**：若 regex 找不到（動態注入），改用 Playwright Chromium headless 執行頁面 JS 後 `page.evaluate("() => LocalSprData")`。

### 正確 import（新程式碼）

```python
from lib.testtool.sleepstudy import SleepReportParser, SleepSession
# 或
from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser, SleepSession
```

### 向下相容 import（舊程式碼，仍可用）

```python
# 以下兩種仍然 work，但不建議用於新程式碼
from lib.testtool.phm.sleep_report_parser import SleepReportParser, SleepSession
from lib.testtool.phm import SleepReportParser, SleepSession
```

### `SleepSession` dataclass 欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `session_id` | `int` | 報告中的 SESSION ID |
| `entry_time_local` | `datetime` | 進入時間（local time，timezone-naive）|
| `exit_time_local` | `datetime` | 離開時間 |
| `duration_seconds` | `float` | 睡眠持續秒數 |
| `sw_pct` | `int\|None` | Software DRIPS %（無資料時為 `None`）|
| `hw_pct` | `int\|None` | Hardware DRIPS %（無資料時為 `None`）|
| `on_ac` | `bool` | `True`=充電，`False`=放電 |
| `duration_hms` | property `str` | 格式化字串如 `"24:13:06"` |

### `SleepReportParser` API

```python
# 建立 parser（檔案不存在立即拋 SleepStudyLogParseError）
parser = SleepReportParser(r"C:\tmp\sleepstudy-report.html")

# 取得所有 Sleep sessions（無過濾）
all_sessions = parser.get_sleep_sessions()

# 依日期過濾（string 或 datetime 均可）
sessions = parser.get_sleep_sessions(
    start_dt="2026-03-04",        # date-only → 00:00:00
    end_dt="2026-03-04",          # date-only end → 23:59:59（自動補）
)

# 精確時間範圍（datetime 物件）
from datetime import datetime, timedelta
sessions = parser.get_sleep_sessions(
    start_dt=datetime(2026, 3, 4, 11, 0),
    end_dt=datetime(2026, 3, 4, 11, 30),
)

# 最近 24 小時
sessions = parser.get_sleep_sessions(
    start_dt=datetime.now() - timedelta(hours=24),
    end_dt=datetime.now(),
)
```

### 回傳結果使用

```python
for s in sessions:
    print(f"SID={s.session_id}  {s.entry_time_local}  "
          f"Duration={s.duration_hms}  SW={s.sw_pct}%  HW={s.hw_pct}%")

# 判斷 SW% 是否符合標準
for s in sessions:
    if s.sw_pct is not None and s.sw_pct < 90:
        print(f"Session {s.session_id} 低 SW DRIPS: {s.sw_pct}%")
```

### 參數型別規則
- `start_dt` / `end_dt` 接受 `str`（ISO-8601）或 `datetime` 物件
- date-only string（`"2026-03-04"`）作為 `start_dt` → `00:00:00`；作為 `end_dt` → `23:59:59`
- `datetime` 物件原樣使用（不做任何轉換）
- 無效格式字串拋出 `SleepStudyLogParseError`

### 資料取自 HTML 內嵌 JSON `LocalSprData.ScenarioInstances`
- Session `Type == 2` = Sleep（只回傳這類）
- `Duration` 單位：100-nanosecond ticks（除以 `1e7` = 秒）
- SW/HW %公式：`round(100 * sw_ticks / dur_ticks / 10)`
- `_raw_data` 快取：第二次呼叫 `get_sleep_sessions()` 不重新解析

---

## 8. 測試架構

### Unit Tests（`tests/unit/lib/testtool/test_sleepstudy/`）
- `test_exceptions.py` — 例外層級、繼承關係
- `test_config.py` — DEFAULT_CONFIG、驗證、merge_config
- `test_controller.py` — subprocess mock、output_path、get_parser、timeout
- `test_sleep_report_parser.py` — 使用 `parser._raw_data = ...` 直接注入 fixture JSON（跳過解析）；或 mock `_extract_json_via_playwright`
- `test_history_cleaner.py` — 全部使用 `tmp_path` fixture（不觸及 System32）；`PermissionError`/`OSError` 以 `patch(Path.unlink)` 模擬；29 個測試

### Integration Tests（`tests/integration/lib/testtool/test_sleepstudy/`）
- `test_sleep_report_parser_integration.py` — 使用 `tmp/sleepstudy-report.html`（真實樣本）；標記 `@pytest.mark.integration` + `@pytest.mark.slow` + `@pytest.mark.requires_sleepstudy`

**Integration test 注意事項：**
- `playwright install chromium` 需先執行（否則 `BrowserType.launch` 拋錯）
- Playwright 為 fallback 路徑（regex 是主路徑）
- 樣本檔 `tmp/sleepstudy-report.html` 含 7 個 Sleep sessions，key sessions：
  - SID=6：2026-03-02，~24h，SW=100%，HW=100%（Drain）
  - SID=21：2026-03-04 11:06，~91s，SW=98%，HW=98%（Charge）
  - SID=27：2026-03-04 11:59，~62s，SW=0%（Charge）
  - SID=10/15/18/24：短 sleep，無 SW/HW metadata（`sw_pct=None`）

---

## 9. PHM 整合說明

PHM (`lib.testtool.phm`) 的 `pep_checker.py` 使用 `SleepReportParser` 驗證 Sleep Session SW DRIPS%。  
自遷移後，`pep_checker.py` 改為直接 import `lib.testtool.sleepstudy`：

```python
# lib/testtool/phm/pep_checker.py
from lib.testtool.sleepstudy import SleepReportParser
```

**PHM backward-compat shim（`lib/testtool/phm/sleep_report_parser.py`）：**
```python
# re-export shim — 勿在新程式碼使用
from lib.testtool.sleepstudy.sleep_report_parser import (
    SleepReportParser, SleepSession, SESSION_TYPE_SLEEP, _TICKS_PER_SECOND
)
```

---

## 10. 相關路徑

| 資源 | 路徑 |
|------|------|
| 套件程式碼 | `lib/testtool/sleepstudy/` |
| History Cleaner | `lib/testtool/sleepstudy/history_cleaner.py` |
| PHM shim（向下相容） | `lib/testtool/phm/sleep_report_parser.py` |
| Sleep Study 樣本 HTML | `tmp/sleepstudy-report.html` |
| Unit Tests | `tests/unit/lib/testtool/test_sleepstudy/` |
| History Cleaner Unit Tests | `tests/unit/lib/testtool/test_sleepstudy/test_history_cleaner.py` |
| Integration Tests | `tests/integration/lib/testtool/test_sleepstudy/` |
| PHM backward-compat Tests | `tests/unit/lib/testtool/test_phm/test_sleep_report_parser.py` |
| pytest marker | `requires_sleepstudy` |
| Playwright 文件 | https://playwright.dev/python/docs/intro |
