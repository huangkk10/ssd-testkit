# PHM (Powerhouse Mountain) — Tool Reference

> Source of truth: `PHM_PLAN.md`  
> Ticket: STC-2562  
> Status: SCAFFOLD COMPLETE — 待 PHM 安裝後驗證 UI / Log 格式

---

## 1. 工具概覽

**Powerhouse Mountain (PHM)** 是 Intel 出品的電源管理測試工具。

| 項目 | 值 |
|------|----|
| 用途 | Modern Standby (ACPI S0ix) 電源循環測試、Power Cycling 壓測、PLN 合規驗證 |
| 版本 | 4.22.0 Build 25.02.06.02 H |
| 架構 | **Node.js 後端 + 瀏覽器前端（Web App）** — 非傳統 GUI，pywinauto 無效 |
| UI 自動化工具 | **Playwright**（取代 pywinauto），操作 `http://localhost:1337` |

---

## 2. 安裝資訊

| 項目 | 值 |
|------|----|
| 安裝檔名 | `phm_nda_V4.22.0_B25.02.06.02_H.exe` (382 MB) |
| 安裝檔來源 | `C:\Users\Administrator\Downloads\PHM_4.22.0\PHM_4.22.0\` |
| Integration 測試安裝檔 | `tests/integration/bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe` |
| 靜默安裝 switch | `/S`（NSIS，無 GUI 彈出） |
| 靜默移除 | `phm_setup_nda.exe /uninstall /quiet`（從 Registry `QuietUninstallString` 讀取） |
| **安裝目錄** | **`C:\Program Files\PowerhouseMountain\`** |
| **主程式** | **`C:\Program Files\PowerhouseMountain\PowerhouseMountain.exe`** |
| 啟動 WorkingDirectory | **必須設定為** `C:\Program Files\PowerhouseMountain\` |

### 安裝後 Port（Node.js）

| Port | 用途 |
|------|------|
| `1337` | 主 Web UI / API |
| `1338` | 輔助 API |
| `5999` | 輔助服務 |

### 附屬工具

- **CTA v1.0.1.0** (`ctaProvider`) — 是否需要單獨 library 待確認（Action Item #5）

---

## 3. 套件結構

```
lib/testtool/phm/
├── __init__.py            # 套件入口、exports、使用範例 docstring
├── config.py              # DEFAULT_CONFIG、型別驗證、merge_config()
├── controller.py          # 主控制器（繼承 threading.Thread）
├── exceptions.py          # 例外階層
├── process_manager.py     # 安裝 / 移除 / 啟動 / 停止生命週期
├── log_parser.py          # PHM HTML 測試報告解析
├── sleep_report_parser.py # ⚠️ re-export shim（已遷移至 lib.testtool.sleepstudy，向下相容保留）
├── ui_monitor.py          # Playwright Collector Tab Web UI 自動化
└── visualizer.py          # Playwright Visualizer Tab + REST API 摘要資料抽取與驗證
```

> ⚠️ `log_parser.py` 解析 PHM 自身的測試結果 HTML。
> ⚠️ `sleep_report_parser.py` 已**遷移**至獨立套件 `lib.testtool.sleepstudy`。`phm/sleep_report_parser.py` 現為 re-export shim，向下相容保留。新程式碼請 import `lib.testtool.sleepstudy`，詳見 `references/sleepstudy.md`。
> ⚠️ `ui_monitor.py` 使用 **Playwright**，不是 pywinauto。

---

## 4. 例外階層（`exceptions.py`）

```python
class PHMError(Exception)               # 根例外
class PHMConfigError(PHMError)          # 設定錯誤
class PHMTimeoutError(PHMError)         # 超時
class PHMProcessError(PHMError)         # 程序啟動 / 停止失敗
class PHMInstallError(PHMError)         # 安裝 / 移除失敗
class PHMUIError(PHMError)              # Playwright 互動失敗
class PHMLogParseError(PHMError)        # HTML log 解析失敗
class PHMTestFailedError(PHMError)      # 測試結果 FAIL
PHMSleepReportParseError = SleepStudyLogParseError  # alias（來自 lib.testtool.sleepstudy.exceptions）
```

---

## 5. 設定參數（`config.py` DEFAULT_CONFIG）

| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `installer_path` | `str` | `""` | 安裝檔完整路徑 |
| `install_path` | `str` | `C:\Program Files\PowerhouseMountain` | 安裝目標目錄 |
| `executable_name` | `str` | `PowerhouseMountain.exe` | 主程式執行檔名 |
| `phm_host` | `str` | `localhost` | PHM Web UI 主機 |
| `phm_port` | `int` | `1337` | PHM Web UI Port |
| `browser_headless` | `bool` | `False` | Playwright headless 模式 |
| `browser_timeout` | `int` | `30000` | Playwright 頁面載入超時 (ms) |
| `log_path` | `str` | `./testlog/PHMLog` | HTML log 輸出目錄 |
| `timeout` | `int` | `3600` | 測試超時秒數 |
| `cycle_count` | `int` | `10` | Power Cycling 循環次數 |
| `test_duration_minutes` | `int` | `60` | 測試持續分鐘數 |
| `check_interval_seconds` | `int` | `5` | 狀態輪詢間隔 |
| `enable_modern_standby` | `bool` | `True` | 是否啟用 Modern Standby 模式 |
| `dut_id` | `str` | `"0"` | DUT 裝置 ID |

---

## 6. 模組功能摘要

### `process_manager.py`
- `install()` — 執行 `<installer_path> /S`
- `uninstall()` — 從 Registry `QuietUninstallString` 讀取並執行
- `is_installed()` — 檢測安裝路徑 / Registry 是否存在
- `launch()` — 啟動 `PowerhouseMountain.exe`（需設 WorkingDirectory）
- `terminate()` — 強制結束 PHM 程序

### `log_parser.py`（PHM 測試報告）
- `parse_html_report(html_path: str) -> PHMTestResult`
- `PHMTestResult` dataclass：`status`, `total_cycles`, `completed_cycles`, `errors`, `start_time`, `end_time`, `raw_html_path`
- 解析失敗拋出 `PHMLogParseError`

### `sleep_report_parser.py`（Windows Sleep Study 報告）

Windows `powercfg /sleepstudy` 產生的 HTML 報告解析模組。報告內嵌 `LocalSprData` JSON 物件，包含所有 Session 資料。

**解析策略：**
1. **Regex（主路徑）**：`LocalSprData` 是靜態 JSON literal，regex 快速提取，零延遲。
2. **Playwright fallback**：若 regex 找不到，改用 Playwright Chromium headless 執行頁面 JS 後 `page.evaluate("() => LocalSprData")`。

**主要 Class：**

```python
# ✅ 新程式碼：使用 sleepstudy 套件（canonical）
from lib.testtool.sleepstudy import SleepReportParser, SleepSession
# 或
from lib.testtool.sleepstudy.sleep_report_parser import SleepReportParser, SleepSession

# ⚠️ 舊程式碼（shim，仍可用但不建議）
from lib.testtool.phm.sleep_report_parser import SleepReportParser, SleepSession
from lib.testtool.phm import SleepReportParser, SleepSession
```

> 詳細 API 文件請見 `references/sleepstudy.md`。

**`SleepSession` dataclass 欄位：**

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

**`SleepReportParser` API：**

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

# 精確時間範圍（string）
sessions = parser.get_sleep_sessions(
    start_dt="2026-03-04T11:00:00",
    end_dt="2026-03-04T11:30:00",
)

# datetime 物件（推薦用於程式計算）
from datetime import datetime, timedelta
sessions = parser.get_sleep_sessions(
    start_dt=datetime(2026, 3, 4, 11, 0),
    end_dt=datetime(2026, 3, 4, 11, 30),
)

# 搭配系統時間（最近 24 小時）
sessions = parser.get_sleep_sessions(
    start_dt=datetime.now() - timedelta(hours=24),
    end_dt=datetime.now(),
)

# 今天整天
from datetime import date
today = date.today()
sessions = parser.get_sleep_sessions(
    start_dt=datetime.combine(today, datetime.min.time()),
    end_dt=datetime.now(),
)
```

**回傳結果使用：**
```python
for s in sessions:
    print(f"SID={s.session_id}  {s.entry_time_local}  "
          f"Duration={s.duration_hms}  SW={s.sw_pct}%  HW={s.hw_pct}%")

# 判斷 SW% 是否符合標準
for s in sessions:
    if s.sw_pct is not None and s.sw_pct < 90:
        print(f"Session {s.session_id} 低 SW DRIPS: {s.sw_pct}%")
```

**參數型別規則：**
- `start_dt` / `end_dt` 接受 `str`（ISO-8601）或 `datetime` 物件
- date-only string（`"2026-03-04"`）作為 `start_dt` → `00:00:00`；作為 `end_dt` → `23:59:59`
- `datetime` 物件原樣使用（不做任何轉換）
- 無效格式字串拋出 `SleepStudyLogParseError`（`PHMSleepReportParseError` 為 alias，仍可 catch）

**資料取自 HTML 內嵌 JSON `LocalSprData.ScenarioInstances`：**
- Session `Type == 2` = Sleep（只回傳這類）
- `Duration` 單位：100-nanosecond ticks（除以 `1e7` = 秒）
- SW/HW %公式：`round(100 * sw_ticks / dur_ticks / 10)`
- `_raw_data` 快取：第二次呼叫 `get_sleep_sessions()` 不重新解析

### `ui_monitor.py`（Playwright — Collector Tab）
```python
monitor = PHMUIMonitor(host='localhost', port=1337)
monitor.wait_for_ready(timeout=30)      # 輪詢直到 HTTP 200
monitor.open_browser(headless=False)
monitor.navigate_to_collector()
monitor.set_cycle_count(10)
monitor.set_test_duration(60)
monitor.set_modern_standby_mode(True)
monitor.start_test()
monitor.wait_for_completion(timeout=3600)
monitor.take_screenshot('./testlog/result.png')
monitor.close_browser()
```
> ⚠️ CSS selector / locator 需實際探測確認（用 `playwright codegen` 或 DevTools）
> 詳細 Collector Tab 自動化說明見 `.claude/skills/scaffold-testtool/references/phm_automation_guide.md`

---

### `visualizer.py`（Playwright — Visualizer Tab + REST API 摘要）

**完整功能**：開啟 Chromium → 載入 trace → 切到 Visualizer tab → 在 metric 樹設定 check/expand/exclusive-select → 等待 canvas render → 呼叫 `parserService` REST API 拿摘要數據 → 驗證 column 門檻 → 儲存 CSV/JSON。

#### 公開 API

**`VisualizerConfig` dataclass**（基礎設施設定，所有欄位均有預設值）

| 欄位 | 型別 | 預設 | 說明 |
|------|------|------|------|
| `host` | `str` | `"localhost"` | PHM Web UI 主機 |
| `port` | `int` | `1337` | PHM Web UI Port |
| `api_port` | `int` | `1338` | parserService REST API Port |
| `headless` | `bool` | `False` | Chromium headless 模式 |
| `traces_base_dir` | `Path` | `C:\Program Files\PowerhouseMountain\traces` | Scenario* 資料夾根目錄 |
| `output_dir` | `Path\|None` | `None`（→ `lib/testtool/phm/output`） | CSV/JSON 輸出目錄 |
| `pause_between_steps` | `float` | `1.0` | 步驟間 sleep（秒），0 停用 |
| `save_output` | `bool` | `True` | 是否寫出 CSV + JSON 檔案 |
| `canvas_wait_seconds` | `int` | `20` | canvas render 最大等待秒數 |

**`VisualizerResult` dataclass**（`run_visualizer_check` 回傳值）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `metric_name` | `str` | 被查詢的 metric（如 `"PCIeLPM"`） |
| `device_filter` | `str\|None` | 篩選用子字串 |
| `rows` | `list[dict]` | 篩選後的摘要行（含 `_title` 欄位） |
| `headers` | `list[str]` | 欄位名稱（`["_title", ...]`） |
| `csv_path` | `Path\|None` | 儲存的 CSV 路徑 |
| `json_path` | `Path\|None` | 儲存的 JSON 路徑 |
| `verdicts` | `list[str]` | 每個 threshold 檢查的詳細結果字串 |
| `passed` | `bool` | 全部 threshold 通過則 `True` |

**`run_visualizer_check(...)` 函數參數**

| 參數 | 型別 | 預設 | 說明 |
|------|------|------|------|
| `metric_name` | `str` | `"PCIeLPM"` | Visualizer 樹中的 metric 標籤（也當 API `name=` 參數） |
| `device_filter` | `str\|None` | `"Standard NVM Express Controller"` | 對 metric 的 children 做 exclusive-select；同時過濾 API 回傳的 `Component` 欄位。`None` = 保留全部 |
| `thresholds` | `dict[str, float]\|None` | `None` | **下限** `{col: min_val}`，column 值必須 `>= min_val` |
| `max_thresholds` | `dict[str, float]\|None` | `None` | **上限** `{col: max_val}`，column 值必須 `<= max_val`。非數值（如 `"No LTR"`）自動 skip |
| `config` | `VisualizerConfig\|None` | `None`（→預設值） | 基礎設施設定 |
| `api_metric_name` | `str\|None` | `None`（→同 `metric_name`） | 覆寫 API `name=` 參數（當樹標籤 ≠ API name 時用，如樹 `"PCIe LTR"` vs API `"PCIeLTR"`） |

**例外**
- `RuntimeError` — playwright 未安裝
- `AssertionError` — threshold 未通過 / canvas 未 render / API 回傳空
- `FileNotFoundError` — 找不到 Scenario* 資料夾或 Contents.cycl

#### 使用範例

```python
from lib.testtool.phm.visualizer import VisualizerConfig, run_visualizer_check

cfg = VisualizerConfig(headless=True, save_output=False)

# ── PCIeLPM：Standard NVM，L1.2 至少 90 % ─────────────────────────────────
result = run_visualizer_check(
    metric_name="PCIeLPM",
    device_filter="Standard NVM Express Controller",
    thresholds={"L1.2": 90.0},
    config=cfg,
)
assert result.passed, result.verdicts

# ── PCIeLTR：treeside 標籤 "PCIe LTR"，API name "PCIeLTR"，Min latency ≤ 50 ms ──
result = run_visualizer_check(
    metric_name="PCIe LTR",
    api_metric_name="PCIeLTR",
    device_filter="Standard NVM Express Controller",
    max_thresholds={"Min": 50_000_000},   # 50 ms in ns
    config=cfg,
)
assert result.passed, result.verdicts

# ── 取所有裝置的 PCIeLPM 數據（不驗 threshold，不儲存值） ──────────────────
result = run_visualizer_check(
    metric_name="PCIeLPM",
    device_filter=None,
)
for row in result.rows:
    print(row)

# ── 讀取 rows 欄位 ─────────────────────────────────────────────────────────
# result.rows 是 list[dict]，每筆 row 鍵名對應 API columnDefs
# 第一欄固定為 "_title" = "{metric_name} — {device_filter}"
# 其他欄位名稱視 metric 而定，如 "Component", "L0s", "L1", "L1.1", "L1.2" (LPM)
# 或 "Component", "Min", "Max", "Average" (LTR)
#
# result.headers = ["_title", "Component", "L1.2", ...]  # 欄位有序清單
# result.csv_path / result.json_path — 不為 None 時表示已儲存
```

#### 9 步驟執行流程（內部）

```
Step 0: 找最新 Scenario* 資料夾 → Contents.cycl
Step 1: 開啟 Chromium → goto http://localhost:1337 → 處理 Open Trace（file chooser 或 viewtrace URL）
Step 2: 點擊 Content.phm 連結（CycleSummary 頁面）
Step 3: 切到 Visualizer tab（找 title="Visualize metrics in a timeline" 的 button）
Step 4: uncheck 所有 → check + expand metric_name
Step 5: exclusive-select device_filter 下的 child（若指定）
        → 等 canvas render（最多 canvas_wait_seconds * 2 × 0.5s 輪詢）
Step 6: 呼叫 parserService REST API → getSummaryData?name={api_metric_name}&url={Content.phm}
Step 7: 依 device_filter 過濾 rows
Step 8: 儲存 CSV + JSON（若 save_output=True）
Step 9: 驗證 thresholds / max_thresholds → 回傳 VisualizerResult
```

> **調試技巧**：每一步驟都會在 `output_dir` 下存 `debug_*.html` + `debug_*.png`（`headless=False` 時可視覺觀察），並在 stdout 輸出詳細 log。若 canvas 未 render，可降低 `pause_between_steps=0` 並提高 `canvas_wait_seconds=40`。

> **實際 smoke test 範例**：`tests/verification/phm/smoke_phm_visualizer_pcie_lpm.py`（PCIeLPM）、`smoke_phm_visualizer_pcie_ltr.py`（PCIeLTR）

---

### `controller.py` 執行流程
```
PHMController.run()
  ├─ process_manager.is_installed() → 若未安裝則 install()
  ├─ process_manager.launch()
  ├─ ui_monitor.wait_for_ready()
  ├─ ui_monitor.set_*(params from config)
  ├─ ui_monitor.start_test()
  ├─ loop: check stop_event / timeout → ui_monitor.get_current_status()
  ├─ ui_monitor.wait_for_completion()
  ├─ log_parser.parse_html_report(log_path)
  └─ set status = True/False based on result
```

---

## 7. 使用範例（最終 API）

```python
from lib.testtool.phm import PHMController, PHMConfig
import os

config = PHMConfig.get_default_config()
config.update({
    "installer_path": os.environ.get("PHM_INSTALLER_PATH",
        "./bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe"),
    "cycle_count": 100,
    "enable_modern_standby": True,
    "log_path": "./testlog/PHMLog",
    "timeout": 7200,
})

controller = PHMController(**config)
controller.start()
controller.join()

assert controller.status is True, f"PHM test failed: {controller.error_count} errors"
```

---

## 8. 測試架構

### Unit Tests（`tests/unit/lib/testtool/test_phm/`）
- **完全 Mock**，不執行安裝，不存取真實檔案系統
- `subprocess.run/Popen` → mock；`winreg.OpenKey` → mock；`playwright.sync_playwright` → mock
- `test_log_parser.py`：使用 fixture HTML 字串（在 `conftest.py` 定義），不依賴真實 HTML
- `test_sleep_report_parser.py`：透過 `parser._raw_data = ...` 直接注入 fixture JSON（跳過解析），或 mock `_extract_json_via_playwright`

### Integration Tests（`tests/integration/lib/testtool/test_phm/`）
- `test_phm_workflow.py`：需要真實 PHM 安裝（安裝檔 382 MB，已加入 `.gitignore`）
- `test_sleep_report_parser_integration.py`：使用 `tmp/sleepstudy-report.html`（已有真實樣本）；啟動真實 Playwright Chromium；標記 `@pytest.mark.integration` + `@pytest.mark.slow`

**Sleep Report integration test 注意事項：**
- `playwright install chromium` 需先執行（否則 `BrowserType.launch` 拋錯）
- Playwright 為 fallback 路徑（regex 是主路徑）；integration test 的 `TestDataCaching` 驗證快取行為
- 樣本檔 `tmp/sleepstudy-report.html` 含 7 個 Sleep sessions，key sessions：
  - SID=6：2026-03-02，~24h，SW=100%，HW=100%（Drain）
  - SID=21：2026-03-04 11:06，~91s，SW=98%，HW=98%（Charge）
  - SID=27：2026-03-04 11:59，~62s，SW=0%（Charge）
  - SID=10/15/18/24：短 sleep，無 SW/HW metadata（`sw_pct=None`）

---

## 9. 待確認事項

| # | 問題 | 狀態 |
|---|------|------|
| 3 | PHP HTML log 實際輸出格式（需取樣本） | ⏳ 待確認 |
| 4 | UI 元素 CSS selector / locator（Playwright `codegen`） | ⏳ 待探測 |
| 5 | CTA v1.0.1.0 是否需要單獨 library | ⏳ 待確認 |
| 7 | Modern Standby 是否需要特定 BIOS 設定 | ⏳ 待確認 |

---

## 10. 相關路徑

| 資源 | 路徑 |
|------|------|
| 開發計畫（詳細） | `PHM_PLAN.md` |
| 套件程式碼 | `lib/testtool/phm/` |
| Visualizer 模組 | `lib/testtool/phm/visualizer.py` |
| Visualizer smoke tests | `tests/verification/phm/smoke_phm_visualizer_pcie_lpm.py`、`smoke_phm_visualizer_pcie_ltr.py` |
| Sleep Study 解析模組（canonical） | `lib/testtool/sleepstudy/` |
| Sleep Study 解析模組（PHM shim） | `lib/testtool/phm/sleep_report_parser.py`（re-export shim） |
| Sleep Study 樣本 HTML | `tmp/sleepstudy-report.html` |
| Sleep Report Unit Tests（canonical） | `tests/unit/lib/testtool/test_sleepstudy/test_sleep_report_parser.py` |
| Sleep Report Integration Tests（canonical） | `tests/integration/lib/testtool/test_sleepstudy/test_sleep_report_parser_integration.py` |
| Sleep Report PHM backward-compat Tests | `tests/unit/lib/testtool/test_phm/test_sleep_report_parser.py` |
| SleepStudy Tool Reference | `.claude/skills/scaffold-testtool/references/sleepstudy.md` |
| Integration 安裝檔 | `tests/integration/bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe` |
| Integration Config | `tests/integration/Config/Config.json` → `"phm"` 區塊 |
| Playwright 文件 | https://playwright.dev/python/docs/intro |
