# OsConfig — Tool Reference

> Source of truth: `OSCONFIG_PLAN.md`  
> Status: ALL 6 PHASES COMPLETE — 403 unit + 33 integration tests passed (2026-03-03)

---

## 1. 工具概覽

`lib/testtool/osconfig/` 是純 Python API 套件，統一管理 Windows OS 層級設定。
**無外部 executable**，透過 `winreg` + `subprocess`（PowerShell）操作系統。

| 項目 | 值 |
|------|----|
| 用途 | 停用 Search Index、OneDrive、Defender、設定電源計畫、停用自動更新等 34 種 OS 設定，並可完整還原 |
| 執行類型 | `api`（純 Python，無外部 exe） |
| 需要安裝 | ❌ |
| 有 GUI | ❌ |
| 特殊模組 | `os_compat.py`（版本相容），`registry_helper.py`（winreg CRUD），`state_manager.py`（snapshot/revert），`actions/`（34 個 Action 類別） |

### 重要特性

- **Fail-soft**：不支援的 OS 功能 → log warning + skip，不 raise（可選 `fail_on_unsupported=True`）
- **Idempotent**：`apply()` 前先 `check()`，已是目標狀態不重複寫入
- **Snapshot/Revert**：`apply()` 前自動 snapshot 到 JSON，`revert()` 完整還原
- **Defender Tamper Protection fallback**：先嘗試 `Set-MpPreference`（PowerShell）→ registry → warn

---

## 2. 套件結構

```
lib/testtool/osconfig/
├── __init__.py              # exports OsConfigController, OsConfigProfile, exceptions
├── config.py                # OsConfigProfile dataclass（34 個 bool/str 參數）
├── controller.py            # OsConfigController(threading.Thread)
├── exceptions.py            # 例外階層
├── os_compat.py             # 版本偵測 + Capability Matrix
├── registry_helper.py       # winreg CRUD（完全可 mock）
├── state_manager.py         # snapshot / revert JSON
└── actions/
    ├── base_action.py               # AbstractOsAction（apply/revert/check/supported_on）
    ├── _base_service_action.py      # 服務類共用基底
    ├── _helpers.py                  # 內部 helper
    │── 服務類（6 個）──
    ├── search_index.py              # SearchIndexAction
    ├── sysmain.py                   # SysMainAction
    ├── windows_update.py            # WindowsUpdateAction
    ├── wer.py                       # WerAction
    ├── telemetry.py                 # TelemetryAction
    ├── pcasvc.py                    # PcaSvcAction
    │── OneDrive（RS1+ guard）──
    ├── onedrive.py                  # OneDriveAction（build ≥ 14393）
    │── 安全類（6 個）──
    ├── defender.py                  # DefenderAction（PS fallback）
    ├── memory_integrity.py          # MemoryIntegrityAction
    ├── vuln_driver_blocklist.py     # VulnDriverBlocklistAction
    ├── firewall.py                  # FirewallAction
    ├── uac.py                       # UacAction
    │── 開機類（5 個）──
    ├── test_signing.py              # TestSigningAction（bcdedit）
    ├── recovery.py                  # RecoveryAction（bcdedit）
    ├── auto_reboot.py               # AutoRebootAction
    ├── auto_admin_logon.py          # AutoAdminLogonAction
    ├── memory_dump.py               # MemoryDumpAction
    │── 電源類（3 個）──
    ├── power_plan.py                # PowerPlanAction
    ├── power_timeout.py             # PowerTimeoutAction（AC/DC monitor/standby/hibernate/disk）
    ├── unattended_sleep.py          # UnattendedSleepAction
    ├── hibernation.py               # HibernationAction（powercfg /h off）
    │── 排程類（2 個）──
    ├── defrag_schedule.py           # DefragScheduleAction
    ├── defender_scan_schedule.py    # DefenderScanScheduleAction
    │── 系統類（6 個）──
    ├── system_restore.py            # SystemRestoreAction
    ├── fast_startup.py              # FastStartupAction
    ├── notifications.py             # NotificationAction
    ├── cortana.py                   # CortanaAction
    ├── background_apps.py           # BackgroundAppsAction
    └── pagefile.py                  # PagefileAction
```

---

## 3. 例外階層（`exceptions.py`）

```python
class OsConfigError(Exception)
class OsConfigPermissionError(OsConfigError)   # 需要管理員權限
class OsNotSupportedError(OsConfigError)       # 目前 OS 版本不支援此功能
class OsConfigStateError(OsConfigError)        # snapshot/revert 狀態錯誤
class OsConfigActionError(OsConfigError)       # 單個 Action apply/revert 失敗
```

---

## 4. 設定參數（`OsConfigProfile` — 34 個）

所有參數預設 `False`（全不啟用），只設定需要的項目。

| 分類 | 參數 | 說明 |
|------|------|------|
| **服務** | `disable_search_index` | 停用 WSearch |
| | `disable_sysmain` | 停用 SysMain/Superfetch |
| | `disable_windows_update` | 停用 wuauserv |
| | `disable_wer` | 停用 Windows Error Reporting |
| | `disable_telemetry` | 停用 DiagTrack |
| | `disable_pcasvc` | 停用 Program Compatibility Assistant |
| **OneDrive** | `disable_onedrive_metered` | 停用 OneDrive metered sync（RS1+） |
| | `disable_onedrive_filesync` | 停用 OneDrive file storage（RS1+） |
| **安全** | `disable_defender` | 停用 Defender Real-time（PS fallback） |
| | `disable_memory_integrity` | 停用 Core Isolation |
| | `disable_vuln_driver_blocklist` | 停用 Vulnerable Driver Blocklist |
| | `disable_firewall` | 停用 Firewall（所有 profile） |
| | `disable_uac` | 停用 UAC |
| **開機** | `enable_test_signing` | 啟用 Test Signing（bcdedit） |
| | `disable_recovery` | 停用 Recovery Mode（bcdedit） |
| | `disable_auto_reboot` | 停用 BSOD 後自動重開機 |
| | `enable_auto_admin_logon` | 啟用自動管理員登入 |
| | `enable_small_memory_dump` | 啟用 Small Memory Dump |
| **電源** | `power_plan` | `"high_performance"` / `"balanced"` / `"power_saver"` |
| | `disable_monitor_timeout` | 停用螢幕逾時（AC + DC） |
| | `disable_standby_timeout` | 停用待機逾時 |
| | `disable_hibernate_timeout` | 停用休眠逾時 |
| | `disable_disk_timeout` | 停用磁碟逾時 |
| | `disable_unattended_sleep` | 停用自動睡眠 |
| | `disable_hibernation_file` | 停用休眠檔（`powercfg /h off`） |
| **排程** | `disable_defrag_schedule` | 停用磁碟重組排程 |
| | `disable_defender_scan_schedule` | 停用 Defender 掃描排程 |
| **系統** | `disable_system_restore` | 停用系統還原 |
| | `disable_fast_startup` | 停用快速啟動 |
| | `disable_notifications` | 停用 Windows 通知 |
| | `disable_cortana` | 停用 Cortana |
| | `disable_background_apps` | 停用背景應用程式 |
| | `configure_pagefile` | 設定虛擬記憶體 |
| **全域** | `fail_on_unsupported` | 遇到不支援項目是否 raise（預設 `False`） |

---

## 5. Controller 介面（`controller.py`）

```python
class OsConfigController(threading.Thread):
    def __init__(self, profile: OsConfigProfile, **kwargs): ...
    def apply_all(self) -> None:    # snapshot → 所有 True 的 Action.apply()
    def revert_all(self) -> None:   # 從 snapshot JSON 還原所有 Action.revert()
    def run(self) -> None:          # thread body（呼叫 apply_all）
    def stop(self) -> None:
    @property
    def status(self) -> Optional[bool]: ...   # None=執行中, True=Pass, False=Fail
```

---

## 6. `AbstractOsAction` 介面

每個 Action 都實作：

```python
class AbstractOsAction(ABC):
    def apply(self) -> None: ...          # 套用設定
    def revert(self) -> None: ...         # 還原（依 snapshot）
    def check(self) -> bool: ...          # 目前是否已在目標狀態
    @classmethod
    def supported_on(cls, build_info: WindowsBuildInfo) -> bool: ...  # 該版本是否支援
```

---

## 7. `os_compat.py` — 版本相容

```python
@dataclass
class WindowsBuildInfo:
    major: int       # 10
    build: int       # 19045
    edition: str     # "Home" / "Pro" / "Enterprise"
    version_tag: str # "win10" / "win11"

def get_build_info() -> WindowsBuildInfo: ...
def is_supported(feature: str, build_info: WindowsBuildInfo) -> bool: ...
```

版本 guard 示例：
- `onedrive_metered` — 需要 build ≥ 14393（RS1）
- `defender_tamper_protection_api` — 需要 build ≥ 18362（1903）

---

## 8. 使用範例

### 基本用法

```python
from lib.testtool.osconfig import OsConfigController, OsConfigProfile

profile = OsConfigProfile(
    disable_search_index=True,
    disable_windows_update=True,
    disable_defender=True,
    power_plan="high_performance",
    disable_monitor_timeout=True,
    disable_standby_timeout=True,
    disable_fast_startup=True,
)

controller = OsConfigController(profile=profile)
controller.apply_all()   # 套用所有設定（自動 snapshot）

# ... 執行測試 ...

controller.revert_all()  # 完整還原
```

### threading 模式

```python
controller = OsConfigController(profile=profile)
controller.start()
controller.join()
assert controller.status is True
```

### 單獨使用 Action

```python
from lib.testtool.osconfig.actions.search_index import SearchIndexAction
from lib.testtool.osconfig.os_compat import get_build_info

build = get_build_info()
action = SearchIndexAction(registry_helper=..., build_info=build)
if action.supported_on(build) and not action.check():
    action.apply()
```

---

## 9. Integration Tests 注意事項

| 測試類別 | 需管理員 | 需重開機 | 說明 |
|---------|---------|---------|------|
| 服務類（5 個） | ✅ | ❌ | search_index, sysmain, wer, telemetry, pcasvc |
| 電源類 | ✅ | ❌ | power_plan, timeouts |
| 排程類 | ✅ | ❌ | defrag, defender scan |
| 系統類 | ✅ | ❌ | fast_startup, notifications, cortana, background_apps |
| 開機類（部分）| ✅ | ❌（registry only）| auto_reboot, memory_dump |
| **排除項目** | — | — | windows_update, defender（Tamper Protection）, memory_integrity（HVCI）, test_signing（bcdedit）, hibernation, uac |

執行指令：
```powershell
# 全部 integration tests（需管理員）
pytest tests/integration/osconfig/ -m "integration and admin" -v

# 單類別
pytest tests/integration/osconfig/test_integration_services.py -v
```

---

## 10. 相關路徑

| 資源 | 路徑 |
|------|------|
| 開發計畫（詳細） | `OSCONFIG_PLAN.md` |
| 套件程式碼 | `lib/testtool/osconfig/` |
| Actions 目錄 | `lib/testtool/osconfig/actions/` （34 個 action 檔案） |
| Unit Tests | `tests/unit/lib/testtool/test_osconfig/` |
| Integration Tests | `tests/integration/osconfig/` |
