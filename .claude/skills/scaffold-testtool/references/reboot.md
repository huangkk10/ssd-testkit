# OsReboot — Tool Reference

> Source of truth: `REBOOT_PLAN.md`  
> Status: SCAFFOLD COMPLETE

---

## 1. 工具概覽

`lib/testtool/reboot/` 封裝 Windows 內建 `shutdown.exe /r /t <seconds>` 指令，
提供多次循環重開機控制，並透過 `state_manager.py` 實現**跨重開機的狀態持久化**。

| 項目 | 值 |
|------|----|
| 用途 | OS 重開機循環控制，驗證 SSD 在多次 reboot 下的穩定性 |
| 執行類型 | CLI（`shutdown.exe`，Windows 內建，無需安裝） |
| 需要安裝 | ❌ |
| 有 GUI | ❌ |
| 需產生腳本 | ❌ |
| 結果解析 | 無（依 cycle 完成數判斷 Pass/Fail） |
| **特殊模組** | **`state_manager.py`**（非標準 scaffold 模組，跨重開機狀態持久化） |

---

## 2. 套件結構

```
lib/testtool/reboot/
├── __init__.py          # 套件入口，exports，usage docstring
├── config.py            # DEFAULT_CONFIG、validate_config()、merge_config()
├── controller.py        # OsRebootController(threading.Thread)
├── exceptions.py        # 例外階層
└── state_manager.py     # 狀態持久化（跨重開機的 reboot count 追蹤）
```

---

## 3. 例外階層（`exceptions.py`）

```python
class OsRebootError(Exception)               # 根例外
class OsRebootConfigError(OsRebootError)     # 設定驗證失敗
class OsRebootTimeoutError(OsRebootError)    # 等待 shutdown 命令超時
class OsRebootProcessError(OsRebootError)    # shutdown.exe 回傳非零 exit code
class OsRebootStateError(OsRebootError)      # 狀態檔讀寫失敗
class OsRebootTestFailedError(OsRebootError) # 最終 Pass/Fail 判定失敗
```

---

## 4. 設定參數（`DEFAULT_CONFIG`）

| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `delay_seconds` | `int` | `10` | `shutdown /r /t X` 的 X 值，幾秒後開始 reboot |
| `reboot_count` | `int` | `1` | 總共執行幾次重開機 |
| `state_file` | `str` | `"reboot_state.json"` | 跨重開機狀態檔路徑 |
| `abort_on_fail` | `bool` | `True` | 發生錯誤時是否中止後續 cycle |

---

## 5. Controller 介面（`controller.py`）

```python
class OsRebootController(threading.Thread):
    def __init__(self, **kwargs): ...
    def set_config(self, **kwargs) -> None: ...
    def run(self) -> None: ...
    def stop(self) -> None: ...
    def abort_reboot(self) -> None: ...         # 執行 shutdown /a 取消排程重開機

    @property
    def status(self) -> Optional[bool]: ...     # None=執行中, True=PASS, False=FAIL
    @property
    def current_cycle(self) -> int: ...         # 目前已完成次數
    @property
    def is_recovering(self) -> bool: ...        # 是否為重開機後的恢復狀態
```

### 執行流程

```
OsRebootController.run()
│
├─[is_recovering=True]  → 從 state_manager 恢復 current_cycle
│                          current_cycle >= reboot_count ?
│                          ├─ Yes → status = True（全部完成，PASS）
│                          └─ No  → 繼續下一輪
│
└─[is_recovering=False] → current_cycle = 0，初始化 state_manager
                          LOOP（current_cycle < reboot_count）:
                            state_manager.save(current_cycle)   # 先存狀態
                            subprocess: shutdown /r /t <delay_seconds>
                            等待 OS reboot（程序終止，系統重開機）
                            [重開機後由 framework 重新啟動測試]
                            is_recovering=True → 回到恢復邏輯
```

---

## 6. `state_manager.py`（`OsRebootStateManager`）

跨重開機需將狀態寫入磁碟，確保重開機後能繼續計數。

```python
class OsRebootStateManager:
    def __init__(self, state_file: str): ...
    def load(self) -> dict: ...              # 讀取狀態，不存在則回傳預設值
    def save(self, state: dict) -> None: ... # 寫入並 fsync
    def clear(self) -> None: ...             # 刪除狀態檔（測試結束後清理）
    def is_recovering(self) -> bool: ...     # 判斷是否為重開機後恢復執行
```

**狀態檔格式（JSON）：**
```json
{
  "is_recovering": true,
  "current_cycle": 2,
  "total_cycles": 3,
  "last_reboot_timestamp": "2026-03-02T10:30:00"
}
```

---

## 7. 與 `framework/reboot_manager.py` 的分工

| 元件 | 職責 |
|------|------|
| `framework/reboot_manager.py` | pytest 層的測試狀態恢復（跨 pytest session） |
| `lib/testtool/reboot/` | 工具層的 reboot 發令與 cycle 控制（threading.Thread） |

兩者**互補不衝突**：framework 負責恢復 pytest session，testtool 負責發出 reboot 指令與計次。

---

## 8. 使用範例

```python
from lib.testtool.reboot import OsRebootController

# 5 秒後重開機，共重開 3 次
ctrl = OsRebootController(
    delay_seconds=5,
    reboot_count=3,
    state_file="./testlog/reboot_state.json",
)
ctrl.start()
ctrl.join(timeout=60)

print(ctrl.status)        # True = PASS（全部完成）
print(ctrl.current_cycle) # 目前已完成幾次
```

---

## 9. 測試架構

### Unit Tests（`tests/unit/lib/testtool/test_reboot/`）
```
├── __init__.py
├── conftest.py           # temp_dir fixture、sample_config fixture
├── test_exceptions.py    # 例外繼承關係、raise/catch
├── test_config.py        # DEFAULT_CONFIG、validate、merge
├── test_controller.py    # mock subprocess、mock state_manager
└── test_state_manager.py # 讀寫狀態檔、is_recovering 判斷
```
**完全 Mock** — `subprocess.run/Popen` mock；JSON 讀寫使用 temp dir

### Integration Tests（`tests/integration/lib/testtool/test_reboot/`）
> ⚠️ 實際執行 `shutdown /r` 會導致系統重開機，**需要在隔離測試機或 VM 上執行**。  
> 必須設定環境變數 `ENABLE_REBOOT_INTEGRATION_TEST=1` 才會執行。

---

## 10. 相關路徑

| 資源 | 路徑 |
|------|------|
| 開發計畫（詳細） | `REBOOT_PLAN.md` |
| 套件程式碼 | `lib/testtool/reboot/` |
| Framework 對應元件 | `framework/reboot_manager.py` |
