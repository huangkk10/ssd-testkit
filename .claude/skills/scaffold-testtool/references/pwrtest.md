# PwrTest — Tool Reference

> Source of truth: `PWRTEST_PLAN.md`  
> Status: SCAFFOLD COMPLETE

---

## 1. 工具概覽

`pwrtest.exe` 是 Microsoft WDK 附帶的電源管理測試工具，**已隨 SmiWinTools 一起納入專案**，無需另行安裝。

| 項目 | 值 |
|------|----|
| 用途 | 驅動 OS 進入 Sleep（S3 / Modern Standby S0ix）並設定喚醒時間，驗證 SSD 在 Sleep/Resume 週期下的穩定性 |
| 執行類型 | CLI (`pwrtest.exe /sleep ...`) |
| 需要安裝 | ❌ 已隨 SmiWinTools 附帶 |
| 有 GUI | ❌ 純 CLI |
| 需產生腳本 | ❌ |
| 結果解析 | ✅ `log_file`（`pwrtestlog.log` / `pwrtestlog.xml`） |
| 特殊模組 | `log_parser.py`（非標準 scaffold 模組） |

---

## 2. 執行檔位置

```
tests/unit/lib/testtool/bin/SmiWinTools/bin/x64/pwrtest/
├── win7/
│   └── <version>/pwrtest.exe
├── win10/
│   ├── 1709/pwrtest.exe
│   ├── 1803/pwrtest.exe
│   ├── 1809/pwrtest.exe
│   ├── 1903/pwrtest.exe
│   ├── 1909/pwrtest.exe
│   └── 2004/pwrtest.exe
└── win11/
    ├── 21H2/pwrtest.exe
    ├── 22H2/pwrtest.exe
    ├── 24H2/pwrtest.exe
    └── 25H2/pwrtest.exe     ← 預設使用
```

路徑由 `os_name` + `os_version` 自動組合：  
`<pwrtest_base_dir>/<os_name>/<os_version>/pwrtest.exe`

也可透過 `executable_path` 直接指定完整路徑，或用環境變數 `PWRTEST_EXE_PATH` 覆蓋。

---

## 3. CLI 呼叫語法

```
pwrtest.exe /sleep [/c:<count>] [/d:<delay_sec>] [/p:<wake_after_sec>]
```

| 參數 | config 欄位 | 預設值 | 說明 |
|------|-------------|--------|------|
| `/c` | `cycle_count` | `1` | 執行幾次 sleep cycle |
| `/d` | `delay_seconds` | `10` | 進入 sleep 前延遲（秒） |
| `/p` | `wake_after_seconds` | `30` | sleep 後多久喚醒（秒） |

範例組裝：
```python
cmd = [
    str(exe_path),
    "/sleep",
    f"/c:{config['cycle_count']}",
    f"/d:{config['delay_seconds']}",
    f"/p:{config['wake_after_seconds']}",
]
```

---

## 4. 套件結構

```
lib/testtool/pwrtest/
├── __init__.py          # 匯出 PwrTestController, PwrTestConfig, 例外類別
├── config.py            # DEFAULT_CONFIG、validate_config()、merge_config()
├── controller.py        # PwrTestController(threading.Thread)
├── exceptions.py        # PwrTestError 階層（含 PwrTestLogParseError）
└── log_parser.py        # 解析 pwrtestlog.log / pwrtestlog.xml
```

---

## 5. 例外階層（`exceptions.py`）

```python
class PwrTestError(Exception)
class PwrTestConfigError(PwrTestError)
class PwrTestTimeoutError(PwrTestError)
class PwrTestProcessError(PwrTestError)
class PwrTestLogParseError(PwrTestError)     # 解析 log/xml 失敗
```

---

## 6. 設定參數（`DEFAULT_CONFIG`）

| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `executable_path` | `str` | `""` | 完整 exe 路徑；空字串時自動組合 |
| `pwrtest_base_dir` | `str` | `./tests/unit/lib/testtool/bin/SmiWinTools/bin/x64/pwrtest` | SmiWinTools 內 pwrtest 根目錄 |
| `os_name` | `str` | `"win11"` | `win7` / `win10` / `win11` |
| `os_version` | `str` | `"25H2"` | 對應 OS 下的子目錄（如 `25H2`、`2004`） |
| `cycle_count` | `int` | `1` | sleep cycle 次數（`/c`） |
| `delay_seconds` | `int` | `10` | 進入 sleep 前延遲（`/d`） |
| `wake_after_seconds` | `int` | `30` | sleep 後喚醒時間（`/p`） |
| `log_path` | `str` | `"./testlog/PwrTestLog"` | log 輸出目錄 |
| `log_prefix` | `str` | `""` | log 檔名前綴 |
| `timeout_seconds` | `int` | `300` | 整體 timeout（應 > `cycle_count*(delay+wake)`） |
| `check_interval_seconds` | `float` | `2.0` | process 輪詢間隔（秒） |

**已知 OS 版本常數：**
```python
KNOWN_OS_VERSIONS = {
    "win7":  [],
    "win10": ["1709", "1803", "1809", "1903", "1909", "2004"],
    "win11": ["21H2", "22H2", "24H2", "25H2"],
}
```

---

## 7. `log_parser.py` 輸出格式

```python
{
    "passed": bool,
    "cycles_attempted": int,
    "cycles_passed": int,
    "cycles_failed": int,
    "errors": list[str],
    "raw_summary": str,
}
```

Pass 關鍵字：`PASS` / `Passed`  
Fail 關鍵字：`FAIL` / `Failed` / `Error`

---

## 8. Controller 執行流程

```
PwrTestController.run()
├── _validate_and_prepare()    # 組合 exe 路徑、建立 log 目錄
├── _build_command()           # 組裝 CLI 參數列表
├── _start_process()           # subprocess.Popen 啟動
├── _monitor_process()         # 輪詢 process，偵測 timeout / crash
└── _collect_results()         # 呼叫 log_parser，設定 self.status
```

公開 API：
- `status: Optional[bool]` — `None`（執行中）/ `True`（Pass）/ `False`（Fail）
- `stop()` — 優雅終止（先 terminate，再 kill）
- `result_summary: dict` — cycle 數、Pass/Fail、log 路徑

---

## 9. 使用範例

```python
from lib.testtool.pwrtest import PwrTestController, PwrTestConfig

config = PwrTestConfig.get_default_config()
config.update({
    "os_name": "win11",
    "os_version": "25H2",
    "cycle_count": 3,
    "delay_seconds": 10,
    "wake_after_seconds": 30,
    "log_path": "./testlog/PwrTestLog",
})

controller = PwrTestController(**config)
controller.start()
controller.join()

assert controller.status is True, f"PwrTest failed: {controller.result_summary}"
```

---

## 10. 整合測試環境變數

| 環境變數 | 說明 | 預設 |
|----------|------|------|
| `PWRTEST_EXE_PATH` | 完整 exe 路徑覆蓋 | 自動組合 |
| `PWRTEST_OS_NAME` | OS 大版本覆蓋 | `win11` |
| `PWRTEST_OS_VERSION` | OS 小版本覆蓋 | `25H2` |
| `PWRTEST_CYCLE_COUNT` | cycle 數覆蓋 | `1` |
| `PWRTEST_WAKE_AFTER` | 喚醒時間覆蓋（秒） | `30` |

---

## 11. 待確認事項

| # | 問題 | 狀態 |
|---|------|------|
| 1 | win7 目錄下的版本子目錄名稱 | ⏳ 待確認 |
| 2 | `pwrtestlog.log` / `.xml` 的實際 Pass/Fail 關鍵字格式 | ⏳ 待確認 |
| 3 | 是否需支援 Modern Standby `/cs` 模式（除基本 S3） | ⏳ 待確認 |
| 4 | 是否需與 burnin 組合使用（SSD 讀寫中做 sleep cycle） | ⏳ 待確認 |

---

## 12. 相關路徑

| 資源 | 路徑 |
|------|------|
| 開發計畫（詳細） | `PWRTEST_PLAN.md` |
| 套件程式碼 | `lib/testtool/pwrtest/` |
| 執行檔（SmiWinTools） | `tests/unit/lib/testtool/bin/SmiWinTools/bin/x64/pwrtest/` |
