# Windows ADK — Tool Reference

> 工具路徑：`lib/testtool/windows_adk/`
> 操控對象：Windows Assessment Console (WAC) GUI，pywinauto `uia` backend

---

## 1. 工具概覽

**Windows ADK (Assessment and Deployment Kit)** 透過 WAC 執行開機/待機/休眠效能量測。

| 項目 | 值 |
|------|----|
| 用途 | BPFS / BPFB / Standby / Hibernate 效能測試、結果解析與 spec 比對 |
| 執行類型 | GUI（`wac.exe`，pywinauto `uia` backend 自動化） |
| 需要安裝 | ✅ `choco install windows-adk` |
| 有 GUI | ✅ pywinauto（`uia` backend，非 `win32`） |
| 需 reboot | ✅ 部分 assessment 需要多次 reboot（BPFS/BPFB/Standby） |
| 結果解析 | `result_parser.py`（AxeLog.txt + Assessment result XML） |

---

## 2. 套件結構

```
lib/testtool/windows_adk/
├── __init__.py          # export ADKController
├── config.py            # DEFAULT_CONFIG, WAC_EXE, SUPPORTED_BUILDS, thresholds
├── controller.py        # ADKController(threading.Thread) — 主 orchestrator
├── exceptions.py        # 例外階層
├── result_parser.py     # parse AxeLog.txt / result XML
├── result_reader.py     # 讀取 WAC 結果目錄
├── ui_runner.py         # ★ UIRunner — pywinauto WAC UI 自動化（最複雜）
└── version_adapter.py   # 跨 Windows build 路徑差異處理
```

---

## 3. 例外階層（`exceptions.py`）

```python
class ADKError(Exception)
class ADKConfigError(ADKError)    # 設定錯誤
class ADKUIError(ADKError)        # pywinauto UI 操作失敗
class ADKResultError(ADKError)    # 結果缺失/格式錯誤/spec 不符
class ADKTimeoutError(ADKError)   # 操作超時
class ADKProcessError(ADKError)   # 程序操作失敗（kill/connect）
```

---

## 4. 支援的 Windows Build

```python
SUPPORTED_BUILDS = {
    22000: "Windows 11 21H2",
    22621: "Windows 11 22H2/23H2",
    26100: "Windows 11 24H2",      # ← 目前主要測試環境
}
```

---

## 5. ADKController 公開 API

### 使用方式（單 assessment）

```python
from lib.testtool.windows_adk import ADKController

ctrl = ADKController(config={"log_path": "./testlog"})
ctrl.set_assessment("bpfs")          # 或 "bpfb", "standby", "hibernate"
ctrl.start()                          # 非同步執行（threading.Thread）
ctrl.join(timeout=1800)
ok, msg = ctrl.get_result()
assert ok, msg
```

### `set_assessment(name, **kwargs)` 支援的 name

| name | 說明 | kwargs |
|------|------|--------|
| `"bpfs"` | Boot Performance Fast Startup（預設 3 iter） | — |
| `"bpfs_num_iters"` | BPFS 自訂 iter 數（Quick Run） | `num_iters=1`, `auto_boot=True` |
| `"bpfs_configured"` | BPFS Configure Job（儲存 job 再跑） | `num_iters=1`, `auto_boot=True`, `job_name="BPFS_Test"` |
| `"bpfb"` | Boot Performance Full Boot | — |
| `"standby"` | Standby Performance (S3) | — |
| `"modern_standby"` | Modern Standby Performance (CS) | — |
| `"hibernate"` | Hibernate Performance (S4) | — |

### 其他公開方法

```python
ctrl.get_result()       # → (bool, str)
ctrl.get_power_state()  # → "S3" / "CS" / "Unknown"
ctrl.kill_processes()   # @staticmethod：終止 wac.exe / axe.exe
ctrl.cleanup_dirs()     # 清除 WAC 結果目錄
ctrl.save_result()      # 複製結果到 log_path
ctrl.take_screenshot()  # 截圖 WAC 結果畫面
ctrl.reconnect()        # reboot 後重連 WAC
```

---

## 6. 多 assessment 合併 job（S3/S4/S5 組合）

STC-2557 等同時測多種待機模式的 test case，使用 Configure Job 流程：

```python
ctrl = ADKController(config={"log_path": "./testlog"})
ctrl.kill_processes()
ctrl.cleanup_dirs()

ui = ctrl._ui   # 或直接使用 UIRunner()

# 1. 第一個 assessment：Standby（建立 Configure Job tab）
ui.open(WAC_EXE)
ui.add_standby_to_configure_job(num_iters=1)

# 2. 補充其他 assessment（tab 已存在時用 library path）
ui.add_bpfs_to_configure_job(num_iters=1, auto_boot=True)
ui.add_bpfb_to_configure_job(num_iters=1)

# 3. 送出 job
ui.submit_configure_job()
ui.save_custom_job("S3S4S5_Test")
ui.connect_launcher()
ui.click_start()
```

---

## 7. UIRunner — pywinauto 操控要點

### 7.1 Backend 選擇

WAC 是 WPF 應用程式，必須使用 `uia` backend（非 `win32`）：

```python
app = Application(backend="uia").start(WAC_EXE)
window = app.window(title="Windows Assessment Console")
```

### 7.2 auto_id 常數定義（`ui_runner.py` 頂部）

| 常數 | 用途 |
|------|------|
| `_AID_ASSESSMENT` | Quick Run panel 各 assessment 的 `AID_QuickRun_Assessment_<GUID>` |
| `_AID_JOB_CARD` | Configure Job 左排 assessment cards 的 `AID_JobProperties_Assessment_<GUID>` |
| `_AID_ADD_CARD` | Add assessments library panel 各 item 的 `AID_AddAssessment_Assessment_<GUID>` |
| `_AID_LIBRARY_LIST` | `"AID_AddAssessments_AssessmentTileList"` — library panel 的 List 容器 |

> 所有 assessment 的 GUID 相同，只有前綴不同：
> - Quick Run：`AID_QuickRun_Assessment_<GUID>`
> - Configure Job card：`AID_JobProperties_Assessment_<GUID>`
> - Add assessments library：`AID_AddAssessment_Assessment_<GUID>`

### 7.3 WAC 虛擬化列表問題（核心陷阱）

WAC 的 "Add assessments" library panel 使用 **WPF `VirtualizingStackPanel`**。
這代表：

| 方法 | 結果 |
|------|------|
| `window.descendants(control_type="ListItem")` — TreeWalker | ✅ 可以枚舉所有 item，包含未渲染的 |
| `window.child_window(title="Standby performance", ...)` — `FindFirst` | ❌ 找不到 viewport 外的 item → **5s timeout** |
| `item.scroll_into_view()` | ❌ WAC list 不實作 `IScrollItemProvider` → **5s timeout** |
| `item.select()` / `item.set_focus()` | ❌ `FindFirst` 一樣找不到 → **5s timeout** |

**正確做法（已採用）**：

```python
# 1. 找到 List 容器（它在 viewport 內，FindFirst 可以找到）
library_list = window.child_window(
    auto_id="AID_AddAssessments_AssessmentTileList",
    control_type="List",
)
# 2. focus + {END} 鍵 → WPF de-virtualize 底部 items
library_list.set_focus()
keyboard.send_keys("{END}")
time.sleep(0.5)
# 3. 用 auto_id 找目標（現在已在 viewport，FindFirst 可以找到）
item = window.child_window(
    auto_id="AID_AddAssessment_Assessment_d57b93b2-9103-4a98-a8b7-4ca7c5230bbb",
    control_type="ListItem",
)
item.child_window(title="Add assessment", control_type="Button").click_input()
```

### 7.4 ElementAmbiguousError 陷阱

當 library panel 開啟時，同名 assessment 在 UI tree 裡有 **兩個 ListItem**：
- 左排 Configure Job assessments list（`AID_JobProperties_Assessment_...`）
- 右排 Add assessments library（`AID_AddAssessment_Assessment_...`）

解決方案：**永遠用 auto_id 找元素**，不要只用 `title=` 找。

### 7.5 調試方法

```python
# 枚舉所有 ListItem（不受虛擬化影響）
list_items = window.descendants(control_type="ListItem")
titles = [li.window_text() for li in list_items]
logger.debug("visible ListItems (%d): %s", len(titles), titles)

# 輸出完整 UI tree
self._log_wac_topology("label")  # 已內建於 UIRunner
```

---

## 8. 各 assessment 的 GUID 對照

| Assessment | GUID |
|-----------|------|
| Boot performance (Fast Startup) | `9aa625ba-0fc5-4aaa-ab13-6b1b1a29c2cf` |
| Boot performance (Full Boot) | `5a7a1def-2e1f-4a7b-a792-ae5275b6ef92` |
| Standby performance | `d57b93b2-9103-4a98-a8b7-4ca7c5230bbb` |
| Modern Standby Performance | `ec65f64e-55b4-4abc-a196-4c30af672924` |
| Hibernate performance | `bb6ad2d4-d388-4657-abf4-b289ae7723f7` |

---

## 9. 已知問題與修正紀錄

### [2026-04-07] `add_standby_to_configure_job` library path timeout

**症狀**：STEP 8 (configure_s3) 固定 FAIL，`[STEP 8] FAIL | Elapsed: ~6-18s`

**根因**：`child_window(title="Standby performance")` 在 WAC library panel 的 WPF VirtualizingStackPanel 中，因為 "Standby performance" 在 viewport 以下，UIA `FindFirst` 找不到，等 5s 後 timeout。

**修正**：
1. 改找 library List 容器（`_AID_LIBRARY_LIST`），`set_focus()` + `{END}` 鍵強迫捲動
2. 改用 `auto_id=_AID_ADD_CARD["standby"]` 找 ListItem（取代 `title=`）
3. 找 Button 加上 `title="Add assessment"` 更明確

**影響範圍**：僅 `add_standby_to_configure_job` library path（tab already exists 分支）。`add_bpfb_to_configure_job` 和 `add_hibernate_to_configure_job` 因為這些 assessment 排在 library panel 較上方目前不受影響，但如遇相同症狀應套用同樣修正模式。

---

## 10. 相關路徑

| 資源 | 路徑 |
|------|------|
| 套件程式碼 | `lib/testtool/windows_adk/` |
| WAC 執行檔 | `C:\Program Files (x86)\Windows Kits\10\...\wac.exe` |
| 結果目錄（build 26100） | `C:\Data\Test\Microsoft\Axe\Results\` |
| 使用範例 test case | `tests/integration/test_case/stc2557_adk_s3s4s5/` |
