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
├── log_parser.py          # HTML 報告解析（PHM 特有，非標準模組）
└── ui_monitor.py          # Playwright Web UI 自動化
```

> ⚠️ `log_parser.py` 是 PHM **專屬非標準模組**（PHM 輸出 HTML 格式 log），scaffold 不預設建立，需手工新增。  
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

### `log_parser.py`（PHM 專屬）
- `parse_html_report(html_path: str) -> PHMTestResult`
- `PHMTestResult` dataclass：`status`, `total_cycles`, `completed_cycles`, `errors`, `start_time`, `end_time`, `raw_html_path`
- 解析失敗拋出 `PHMLogParseError`

### `ui_monitor.py`（Playwright）
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

### Integration Tests（`tests/integration/lib/testtool/test_phm/`）
- 需要真實安裝（安裝檔 382 MB，已加入 `.gitignore`）
- 六個 Phase：Installation → Launch → UIConfig → Run → LogParser → FullWorkflow

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
| Integration 安裝檔 | `tests/integration/bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe` |
| Integration Config | `tests/integration/Config/Config.json` → `"phm"` 區塊 |
| Playwright 文件 | https://playwright.dev/python/docs/intro |
