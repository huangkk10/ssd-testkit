# osconfig — OS 設定管理工具

在**開發機 / 測試機**上一鍵套用、還原、或重置 Windows OS 設定，
不需要透過 pytest 執行。

---

## 前提條件

- 以 **Administrator 身份**執行（右鍵 → 以系統管理員身份執行）
- Python 3.10+，且位於 `ssd-testkit/.venv` 環境

---

## 快速使用（.bat 雙擊執行）

| 檔案 | 功能 |
|------|------|
| `osconfig_apply.bat` | 套用 `osconfig.yaml` 的設定，並儲存快照 |
| `osconfig_revert.bat` | 從快照還原到套用前的狀態 |
| `osconfig_reset.bat` | 還原到 Windows 出廠預設值（不需快照） |
| `osconfig_status.bat` | 顯示目前狀態 vs 目標設定（唯讀） |

> 所有 .bat 都需以 **Administrator** 身份執行。

---

## 指令說明

```bat
python tools/osconfig/osconfig_tool.py <COMMAND> [OPTIONS]
```

### `apply` — 套用設定

```bat
osconfig_tool.py apply [--config PATH] [--force] [--snapshot PATH]
```

- 套用 yaml 中啟用的設定項目
- 套用前先儲存目前狀態快照（預設：`%TEMP%\osconfig_snapshot.json`）
- 如快照已存在，需先執行 `revert` 或加上 `--force` 覆蓋

### `revert` — 還原至快照

```bat
osconfig_tool.py revert [--config PATH] [--snapshot PATH]
```

- 讀取 `apply` 時儲存的快照，逐項還原至原始狀態
- 還原完成後自動刪除快照

### `reset` — 還原至 Windows 預設值

```bat
osconfig_tool.py reset [--config PATH] [--only ACTION ...]
```

- 不需快照，直接把各設定還原至 Windows 出廠值
- `--config`：只重置 yaml 中涉及的設定項目
- `--only`：只重置指定的 action（例如 `DefenderAction FirewallAction`）

### `status` — 顯示目前狀態

```bat
osconfig_tool.py status [--config PATH]
```

- 唯讀，不修改任何設定
- 逐項顯示「目前狀態是否符合目標設定」
- 顯示快照檔案是否存在

---

## osconfig.yaml 設定檔

`osconfig.yaml` 是給開發機使用的**保守設定**，預設只啟用低風險項目：

```yaml
disable_windows_update: true   # 避免開發中自動重開機
disable_search_index:   true   # 減少背景 I/O
disable_sysmain:        true   # 停用 SuperFetch
disable_fast_startup:   true   # 避免影響重開機測試
disable_defrag_schedule: true  # 停用排程磁碟重組
power_plan:             "balanced"
```

以下項目**預設關閉**（會影響安全性，請謹慎啟用）：

```yaml
disable_defender:  false
disable_firewall:  false
disable_uac:       false
# enable_auto_admin_logon — 需要明文密碼，僅用於 lab 機器
```

---

## 常見流程

### 開發前套用設定

```bat
osconfig_apply.bat
```

### 開發結束還原

```bat
osconfig_revert.bat
```

### 機器設定混亂，直接重置回 Windows 預設

```bat
osconfig_reset.bat
```

### 只重置部分設定

```bat
python tools/osconfig/osconfig_tool.py reset --only FirewallAction UacAction
```

---

## 快照檔案

| 項目 | 預設值 |
|------|--------|
| 路徑 | `%TEMP%\osconfig_snapshot.json` |
| 格式 | JSON，記錄 apply 前各設定的原始狀態 |
| 生命週期 | apply 建立，revert 刪除 |

可用 `--snapshot PATH` 指定自訂路徑（apply / revert / status 均支援）。

---

## 架構說明

```
tools/osconfig/
  osconfig_tool.py      ← CLI 入口（apply / revert / reset / status）
  osconfig.yaml         ← apply 用設定檔（決定要套用哪些設定及其值）
  osconfig_reset.yaml   ← reset 用範圍檔（決定要重置哪些項目，值固定為 Windows 預設）
  osconfig_apply.bat    ┐
  osconfig_revert.bat   │  .bat 包裝，方便雙擊執行
  osconfig_reset.bat    │  （使用 osconfig_reset.yaml）
  osconfig_status.bat   ┘

lib/testtool/osconfig/ ← 核心實作（controller、actions、config 等）
```

實際邏輯全在 `lib/testtool/osconfig/`，本工具只是薄薄的 CLI 包裝層。
