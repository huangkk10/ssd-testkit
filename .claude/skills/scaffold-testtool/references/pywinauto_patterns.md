# pywinauto GUI Automation — General Patterns & Pitfalls

> 適用於所有使用 pywinauto 操控 GUI 工具的 testtool（`has_ui: true`）

---

## 1. Backend 選擇

| Backend | 適用 | 特性 |
|---------|------|------|
| `uia` | WPF、WinForms、UWP、Qt | 依賴 UIA (UI Automation)；使用 `FindFirst` / TreeWalker |
| `win32` | 老式 Win32 / MFC | 使用 WinAPI；不支援 WPF 的 `auto_id` / `control_type` |

**規則**：現代 Windows 應用（WPF / UWP）一律使用 `uia` backend。

```python
app = Application(backend="uia").connect(title_re="MyApp.*")
```

---

## 2. WPF VirtualizingStackPanel — 核心陷阱

### 2.1 問題描述

WPF 列表（`ListBox`、`ListView`）預設使用 `VirtualizingStackPanel`：**只有在 viewport 內的項目才會真正渲染**，viewport 外的項目在 UIA 元素樹中**不存在**。

**症狀**：
- `child_window(title="SomeItem")` timeout（ElementNotFoundError / 5s 後）
- `item.select()` timeout
- `item.set_focus()` timeout
- `item.scroll_into_view()` timeout（WAC 未實作 `IScrollItemProvider`）
- `descendants(control_type="ListItem")` 卻能看到所有項目（包含 off-screen）

> **原因**：`child_window()` 內部使用 `FindFirst`，只搜尋 UIA COM 元素樹（viewport only）。
> `descendants()` 內部使用 **TreeWalker**，可遍歷所有節點包含虛擬化未渲染的項目。

### 2.2 確認方法

加入 debug log，先用 `descendants` 列舉所有 ListItem：

```python
items = list_container.descendants(control_type="ListItem")
logger.debug(f"ListItems ({len(items)}): {[i.window_text() for i in items]}")
```

若 `descendants` 看得到但 `child_window` 找不到 → 確定是 VirtualizingStackPanel 問題。

### 2.3 正確解法：Container Focus + Keyboard Scroll

**步驟**：
1. 用 `auto_id` 找到 **List 容器**（容器本身一定在 viewport，可被 FindFirst 找到）
2. `set_focus()` 給容器（而非給項目）
3. 發送 `{END}` / `{HOME}` 等鍵，讓 WPF 捲動並**渲染**末端項目
4. 等待短暫時間（`time.sleep(0.5)`）讓 UIA 樹更新
5. 用 `auto_id` 找目標項目（auto_id 比 title 穩定，不受多重匹配影響）

```python
# ✅ 正確模式
list_container = window.child_window(
    auto_id="MyList_AID",      # List 容器的 auto_id
    control_type="List",
)
list_container.set_focus()
keyboard.send_keys("{END}")    # 捲動到底部以渲染所有項目
time.sleep(0.5)

target_item = window.child_window(
    auto_id="MyItem_AID",      # 目標項目的 auto_id（比 title 安全）
    control_type="ListItem",
)
target_item.child_window(title="Do something", control_type="Button").click_input()
```

### 2.4 反模式（禁止）

```python
# ❌ 直接用 title 找 off-screen 項目 → timeout
item = window.child_window(title="Standby performance", control_type="ListItem")
item.click_input()

# ❌ scroll_into_view() → 若未實作 IScrollItemProvider 則 timeout
item.scroll_into_view()

# ❌ item 層級的 select()/set_focus() → 需先用 FindFirst 找到 item → timeout
item.select()
item.set_focus()

# ❌ 用 title 在 library panel 開啟時搜尋 → 可能有同 title 的多個元素
window.child_window(title="Boot performance")  # Library item vs Job card → ElementAmbiguousError
```

### 2.5 `auto_id` vs `title` 的選擇

| 方式 | 優點 | 風險 |
|------|------|------|
| `title=` | 可讀性高 | UI 同時顯示 library panel + job card 時，相同 title 可能出現兩次 → `ElementAmbiguousError` |
| `auto_id=` | 唯一穩定 | 需要事先調查（`inspect.exe` / `Accessibility Insights`）；版本更新後可能改變 |

**規則**：在可能有重複 title 的場景（如 WAC 的 Add assessments 面板），**必須使用 `auto_id`**。

---

## 3. 常用 UI 調查工具

| 工具 | 用途 |
|------|------|
| `Accessibility Insights for Windows` | 查看 UIA 元素樹、auto_id、control_type |
| `inspect.exe`（Windows SDK） | 同上，更底層 |
| `pywinauto` topology dump | `app.print_control_identifiers()` 或 `window.dump_tree()` |

**在 `ui_runner.py` 加 debug topology dump**：

```python
def _log_wac_topology(self, label: str) -> None:
    try:
        out = io.StringIO()
        self._session.window.print_control_identifiers(out_stream=out)
        logger.debug(f"[topology] {label}:\n{out.getvalue()}")
    except Exception as e:
        logger.debug(f"[topology] {label}: dump failed: {e}")
```

---

## 4. pywinauto 常見 Exception 對照

| Exception | 原因 | 解法 |
|-----------|------|------|
| `ElementNotFoundError` (5s timeout) | `FindFirst` 找不到元素（off-screen 或不存在） | 確認是否 VirtualizingStackPanel 問題；先 scroll container |
| `ElementAmbiguousError` | 多個元素符合條件（如同 title 出現兩次） | 改用 `auto_id` 或 `found_index` |
| `TimeoutExpired` | `wait()` / `wait_not()` 超時 | 確認 UI 狀態是否如預期；調整 timeout |
| `MatchError` | `title_re` pattern 不符 | 印出實際 window title 確認 |

---

## 5. 模組設計規範（`ui_runner.py` / `ui_monitor.py`）

- pywinauto import 必須包裝在 `try/except ImportError`，供 unit test mock 使用：
  ```python
  try:
      from pywinauto import Application, keyboard
      from pywinauto.findwindows import ElementNotFoundError, ElementAmbiguousError
      _PYWINAUTO_AVAILABLE = True
  except ImportError:
      _PYWINAUTO_AVAILABLE = False
  ```
- 所有 UI 操作在獨立 method 中，不混入業務邏輯
- 常數（auto_id、title 字串）集中定義在檔案頂端（`_AID_*` 命名慣例）
- Timeout 設定有 default 值，允許外部覆蓋（config 傳入）

---

## 6. 實際案例：WAC Add Standby Assessment

> 詳細說明見 `references/windows_adk.md` Section 7.3

**問題**：WAC Add Assessments 面板的 "Standby performance" 在列表底部（off-screen）  
**解法**：
```python
# _AID_LIBRARY_LIST = "AID_AddAssessments_AssessmentTileList"
# _AID_ADD_CARD["standby"] = "AID_AddAssessment_Assessment_d57b93b2..."

library_list = window.child_window(auto_id=_AID_LIBRARY_LIST, control_type="List")
library_list.set_focus()
keyboard.send_keys("{END}")
time.sleep(0.5)
standby_item = window.child_window(auto_id=_AID_ADD_CARD["standby"], control_type="ListItem")
standby_item.child_window(title="Add assessment", control_type="Button").click_input()
```

**失敗歷程**（避免重走）：
1. `scroll_into_view()` → timeout（WAC 未實作 `IScrollItemProvider`）
2. `select()` → timeout（同 FindFirst 問題）
3. `{PGDN}` 鍵 + `child_window(title=)` → `ElementAmbiguousError`（job card 也有相同 title）
4. 正確解法：container `{END}` + `child_window(auto_id=)`
