# 計畫：Linux / Ubuntu OS 設定管理（osconfig Linux 擴充）

**版本**: v0.1  
**日期**: 2026-04-30  
**狀態**: 草稿  
**關聯**: `doc/PLAN_linux_tool_support.md`

---

## 一、現況分析

### 1.1 現有 osconfig 架構（Windows）

```
lib/testtool/osconfig/
  config.py            ← OsConfigProfile (dataclass, 全 Windows 欄位)
  controller.py        ← OsConfigController (呼叫 actions)
  os_compat.py         ← WindowsBuildInfo + 版本偵測 (winreg)
  registry_helper.py   ← Windows Registry 讀寫封裝
  state_manager.py     ← 快照 / 還原狀態
  actions/             ← 30+ 個 Windows 動作類別
    base_action.py     ← AbstractOsAction
    windows_update.py
    defender.py
    firewall.py
    power_plan.py
    search_index.py
    ... (30+ 個)

tools/osconfig/
  osconfig_tool.py     ← CLI 入口 (python)
  osconfig.yaml        ← 開發機設定檔
  osconfig_apply.bat
  osconfig_revert.bat
  osconfig_reset.bat
  osconfig_status.bat
```

### 1.2 現有限制

| 元件 | Windows 限制 |
|------|-------------|
| `os_compat.py` | 直接 `import winreg`，在 Linux 下 import 即崩潰 |
| `registry_helper.py` | 純 Windows Registry API |
| 所有 actions | 使用 `winreg`, PowerShell, `sc.exe`, `bcdedit` 等 Windows 工具 |
| `OsConfigProfile` | 欄位語意全是 Windows 概念 |
| CLI `.bat` 腳本 | 無法在 Linux 執行 |

---

## 二、目標

1. **提供 Ubuntu 22.04 LTS 等效 OS 設定管理**：能以單一指令套用 / 還原 / 狀態確認
2. **對應 Windows 的核心設定項目**：服務、電源、核心參數、安全性
3. **不破壞現有 Windows 架構**：Linux 擴充是加法，現有 Windows 程式碼不改
4. **相同設計模式**：apply / revert / check / reset\_default 介面保持一致
5. **支援 pytest 整合**：可在 `conftest.py` 或測試前後呼叫

---

## 三、Linux vs Windows 設定項目對照

| 類別 | Windows 動作 | Linux 對應動作 | 實作方式 |
|------|-------------|---------------|---------|
| 自動更新 | `WindowsUpdateAction` | `UnattendedUpgradesAction` | `systemctl disable unattended-upgrades` |
| 防毒 / 即時保護 | `DefenderAction` | `AppArmorAction` | `systemctl disable apparmor`（可選） |
| 防火牆 | `FirewallAction` | `UfwAction` | `ufw disable` |
| 崩潰回報 | `WerAction` | `ApportAction` | `systemctl disable apport` |
| 遙測 | `TelemetryAction` | *(Ubuntu 無強制遙測)* | 停用 `ubuntu-advantage-tools` telemetry |
| 搜尋索引 | `SearchIndexAction` | `TrackerdAction` | `systemctl --user disable tracker-*` |
| 背景服務 | `SysMainAction`, `PcaSvcAction` | `AvahiAction` | `systemctl disable avahi-daemon` |
| 電源計劃 | `PowerPlanAction` | `CpuGovernorAction` | `cpupower frequency-set -g performance` |
| 螢幕逾時 | `PowerTimeoutAction` | `ScreenBlankAction` | `gsettings / xset s off` |
| 休眠 | `HibernationAction` | `SuspendAction` | `systemctl mask sleep.target suspend.target` |
| 自動重開機 | `AutoRebootAction` | *(核心參數)* | `kernel.panic_on_oops=0` via sysctl |
| 自動登入 | `AutoAdminLogonAction` | `AutoLoginAction` | 修改 GDM/LightDM 設定 |
| UAC | `UacAction` | `SudoNopasswdAction` | `/etc/sudoers.d/` 無密碼規則 |
| 頁面檔 | `PagefileAction` | `SwapAction` | `swapoff -a` + 修改 `/etc/fstab` |
| 記憶體傾印 | `MemoryDumpAction` | `CoreDumpAction` | `ulimit -c` + `systemd-coredump.conf` |
| 效能計時器 | *(n/a)* | `HugepagesAction` | `echo madvise > /sys/kernel/mm/transparent_hugepage/enabled` |
| I/O 排程器 | *(n/a)* | `IoSchedulerAction` | `echo none > /sys/block/nvme0n1/queue/scheduler` |
| NMI Watchdog | *(n/a)* | `NmiWatchdogAction` | `sysctl kernel.nmi_watchdog=0` |
| 排程磁碟重組 | `DefragScheduleAction` | `FstrimTimerAction` | `systemctl disable fstrim.timer`（測試期間） |

---

## 四、架構設計

### 4.1 目錄結構（新增）

```
lib/testtool/osconfig/
  linux_compat.py          ← LinuxDistroInfo + distro 偵測
  linux_config.py          ← LinuxOsConfigProfile (dataclass)
  linux_controller.py      ← LinuxOsConfigController
  actions/
    linux/                 ← 新增子目錄，全部 Linux action
      __init__.py
      base_linux_action.py ← AbstractLinuxOsAction (繼承 AbstractOsAction)
      unattended_upgrades.py
      ufw.py
      apport.py
      apparmor.py
      cpu_governor.py
      suspend.py
      screen_blank.py
      swap.py
      swappiness.py
      hugepages.py
      io_scheduler.py
      nmi_watchdog.py
      auto_login.py
      sudo_nopasswd.py
      core_dump.py
      avahi.py
      fstrim_timer.py
      tracker.py

tools/osconfig/
  linux/
    osconfig_linux.sh        ← CLI 入口 (bash)
    osconfig_linux.yaml      ← Linux 開發機設定檔
    osconfig_linux_apply.sh
    osconfig_linux_revert.sh
    osconfig_linux_reset.sh
    osconfig_linux_status.sh
```

### 4.2 類別繼承關係

```
AbstractOsAction  (現有，不變)
    └── AbstractLinuxOsAction   (新增)
            ├── UnattendedUpgradesAction
            ├── UfwAction
            ├── ApportAction
            ├── CpuGovernorAction
            ├── SuspendAction
            ├── SwapAction
            ├── SwappinessAction
            ├── IoSchedulerAction
            └── ... (其他 Linux actions)

OsConfigController  (現有，不變)
LinuxOsConfigController  (新增，獨立平行)
```

> **設計原則**：Windows 和 Linux Controller 平行獨立，不合併成同一個 class。  
> `tools/osconfig/osconfig_tool.py` 可加 OS 偵測並委派給對應 Controller，  
> 但 lib 層的兩個 Controller 各自獨立。

### 4.3 `AbstractLinuxOsAction` 介面

```python
class AbstractLinuxOsAction(AbstractOsAction):
    """Linux OS action base class."""

    name: str = "AbstractLinuxOsAction"

    # 取代 Windows 的 WindowsBuildInfo
    @classmethod
    def supported_on(cls, distro_info: "LinuxDistroInfo") -> bool:
        """Return True if this action is supported on the given distro."""
        return True  # 預設支援所有 Linux；子類別可 override

    def run_shell(self, cmd: str, sudo: bool = True) -> tuple[int, str]:
        """Execute shell command; return (returncode, stdout+stderr)."""
        ...

    def systemctl(self, verb: str, unit: str, sudo: bool = True) -> bool:
        """Convenience wrapper: systemctl <verb> <unit>."""
        ...

    def sysctl_set(self, key: str, value: str) -> bool:
        """Write sysctl key=value and persist to /etc/sysctl.d/."""
        ...

    def sysctl_get(self, key: str) -> str:
        """Read current sysctl value."""
        ...
```

### 4.4 `LinuxDistroInfo` 資料結構

```python
@dataclass
class LinuxDistroInfo:
    distro_id: str       # "ubuntu" / "centos" / "debian"
    version: str         # "22.04" / "24.04" / "9"
    codename: str        # "jammy" / "noble" / "Stream"
    arch: str            # "x86_64" / "aarch64"
    glibc_version: str   # "2.35"
    kernel: str          # "5.15.0-125-generic"
    is_root: bool        # os.geteuid() == 0
```

偵測來源：`/etc/os-release`（所有現代 Linux 皆有）。

### 4.5 `LinuxOsConfigProfile` 設定宣告

```python
@dataclass
class LinuxOsConfigProfile:
    # 服務
    disable_unattended_upgrades: bool = False
    disable_apport: bool = False
    disable_avahi: bool = False
    disable_tracker: bool = False

    # 安全性
    disable_ufw: bool = False
    disable_apparmor: bool = False       # 謹慎使用
    enable_sudo_nopasswd: bool = False   # lab 機器專用

    # 電源
    cpu_governor: str = ""               # "performance" / "powersave" / ""
    disable_suspend: bool = False
    disable_screen_blank: bool = False

    # 核心參數
    swappiness: int = -1                 # -1 = 不修改；0~100 = 設定值
    disable_hugepages: bool = False      # 設為 madvise
    nmi_watchdog: bool = False           # disable nmi_watchdog

    # 磁碟 / 測試環境
    disable_swap: bool = False
    io_scheduler: str = ""               # "none" / "mq-deadline" / ""；套用到所有 NVMe
    disable_fstrim_timer: bool = False

    # 使用者
    enable_auto_login: bool = False
    auto_login_user: str = ""

    # 其他
    configure_core_dump: bool = False

    @staticmethod
    def lab_default() -> "LinuxOsConfigProfile":
        """適合 SSD 測試 lab 機器的建議設定。"""
        return LinuxOsConfigProfile(
            disable_unattended_upgrades=True,
            disable_apport=True,
            disable_avahi=True,
            disable_ufw=True,
            cpu_governor="performance",
            disable_suspend=True,
            disable_screen_blank=True,
            swappiness=0,
            disable_hugepages=True,
            nmi_watchdog=True,
            disable_fstrim_timer=True,
            io_scheduler="none",
        )
```

---

## 五、各動作設計細節

### 5.1 服務類（systemd）

這類動作模式相同：

```
apply()   → systemctl stop <unit>; systemctl disable <unit>
revert()  → systemctl enable <unit>; systemctl start <unit>  (若原本是 active)
check()   → systemctl is-enabled <unit> == "disabled"
restore_os_default() → systemctl enable <unit>
```

| 動作 | 服務 unit | 備註 |
|------|----------|------|
| `UnattendedUpgradesAction` | `unattended-upgrades.service`, `apt-daily.service`, `apt-daily-upgrade.service` | 連 timer 一起 disable |
| `ApportAction` | `apport.service` | 同時寫 `/etc/default/apport` → `enabled=0` |
| `AvahiAction` | `avahi-daemon.service`, `avahi-daemon.socket` | |
| `FstrimTimerAction` | `fstrim.timer` | 測試期間避免背景 TRIM |
| `SuspendAction` | mask `sleep.target suspend.target hibernate.target hybrid-sleep.target` | 用 `mask` 而非 `disable` |

### 5.2 核心參數類（sysctl）

持久化方式：寫入 `/etc/sysctl.d/99-ssd-testkit.conf`。

```ini
# /etc/sysctl.d/99-ssd-testkit.conf (由 sysctl_set() 自動生成)
vm.swappiness = 0
kernel.nmi_watchdog = 0
```

| 動作 | sysctl key | lab 建議值 | 說明 |
|------|-----------|-----------|------|
| `SwappinessAction` | `vm.swappiness` | `0` | 幾乎不使用 swap，讓 SSD 測試結果更穩定 |
| `NmiWatchdogAction` | `kernel.nmi_watchdog` | `0` | 減少 NMI 中斷干擾 |

快照（revert）：在 apply 前讀取 `sysctl <key>` 目前值，存入 snapshot dict。

### 5.3 CPU Governor（電源）

```bash
# apply: 對所有 CPU 核心設定
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance > $cpu
done
# 或使用 cpupower:
cpupower frequency-set -g performance

# 持久化（重開機後仍有效）：
echo 'GOVERNOR="performance"' > /etc/default/cpupower
systemctl enable cpupower
```

snapshot：apply 前讀取 `cpu0/cpufreq/scaling_governor` 目前值。

### 5.4 I/O 排程器（NVMe SSD）

```bash
# apply: 找出所有 nvme 裝置
for dev in /sys/block/nvme*; do
    echo none > $dev/queue/scheduler
done

# 持久化（udev rule）：
# /etc/udev/rules.d/60-ssd-testkit-scheduler.rules
# ACTION=="add|change", KERNEL=="nvme[0-9]*", ATTR{queue/scheduler}="none"
```

### 5.5 Swap 管理

```bash
# apply:
swapoff -a
# 快照：記錄目前 /proc/swaps 內容

# revert:
swapon -a  (從 /etc/fstab 重新啟用)
# 或 swapon <device> (從快照)
```

> **注意**：`disable_swap` 只在記憶體夠用的 lab 機器使用；若 RAM < 16GB 不建議開啟。

### 5.6 Auto Login（GDM3）

```ini
# /etc/gdm3/custom.conf
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=labuser
```

```python
# apply(): 修改 /etc/gdm3/custom.conf (configparser)
# revert(): 從快照還原或設 AutomaticLoginEnable=False
# 支援 GDM3（Ubuntu 22.04+）和 LightDM（後備）
```

### 5.7 Transparent Hugepages（THP）

```bash
# apply: 設為 madvise（讓程式自己決定，避免 THP 干擾）
echo madvise > /sys/kernel/mm/transparent_hugepage/enabled

# 持久化：加入 /etc/rc.local 或 systemd service
# snapshot: 目前值 (always / madvise / never)
```

---

## 六、CLI 工具（Linux）

### 6.1 Bash 入口設計

提供 bash 腳本作為 CLI 入口，避免需要預先安裝 Python：

```bash
# tools/osconfig/linux/osconfig_linux.sh
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# 確認 Python 可用
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Run prepare_testcase.sh first." >&2
    exit 1
fi

PYTHON="$REPO_ROOT/.venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON=python3
fi

exec "$PYTHON" "$REPO_ROOT/tools/osconfig/osconfig_linux_tool.py" "$@"
```

### 6.2 YAML 設定檔

```yaml
# tools/osconfig/linux/osconfig_linux.yaml
# Linux lab 機器建議設定

# 服務
disable_unattended_upgrades: true
disable_apport: true
disable_avahi: true
disable_fstrim_timer: true

# 安全性（UFW 在 lab 機器可關）
disable_ufw: true
disable_apparmor: false       # 保守，預設不動

# 電源
cpu_governor: "performance"
disable_suspend: true
disable_screen_blank: true

# 核心參數
swappiness: 0
disable_hugepages: true       # 設為 madvise
nmi_watchdog: true

# 磁碟
io_scheduler: "none"          # NVMe 最佳效能

# 不開啟（需手動評估）
disable_swap: false            # 只在 RAM 充足時開啟
enable_sudo_nopasswd: false
enable_auto_login: false
```

### 6.3 使用方式

```bash
# 套用設定（需 sudo）
sudo bash tools/osconfig/linux/osconfig_linux_apply.sh

# 還原設定
sudo bash tools/osconfig/linux/osconfig_linux_revert.sh

# 顯示目前狀態（不修改）
bash tools/osconfig/linux/osconfig_linux_status.sh

# 還原到 OS 預設
sudo bash tools/osconfig/linux/osconfig_linux_reset.sh

# Python API（從測試程式呼叫）
from lib.testtool.osconfig.linux_config import LinuxOsConfigProfile
from lib.testtool.osconfig.linux_controller import LinuxOsConfigController

profile = LinuxOsConfigProfile.lab_default()
controller = LinuxOsConfigController(profile=profile)
controller.apply_all()
# ... 執行測試 ...
controller.revert_all()
```

---

## 七、與 Windows osconfig 整合（入口統一）

在 `tools/osconfig/osconfig_tool.py` 加入 OS 路由，讓同一個工具可跨平台使用：

```python
# tools/osconfig/osconfig_tool.py (現有，小幅修改)
import platform

def main():
    if platform.system() == "Windows":
        from lib.testtool.osconfig import OsConfigController, OsConfigProfile
        # ... 現有邏輯 ...
    elif platform.system() == "Linux":
        from lib.testtool.osconfig.linux_controller import LinuxOsConfigController
        from lib.testtool.osconfig.linux_config import LinuxOsConfigProfile
        # ... Linux 邏輯 ...
    else:
        print(f"[ERROR] Unsupported OS: {platform.system()}")
        sys.exit(1)
```

> **現有 Windows .bat 腳本不變**；Linux 用 `.sh` 腳本。

---

## 八、pytest 整合

### 8.1 在 conftest.py 使用

```python
# tests/integration/conftest.py（或 Linux 專用 conftest）
import pytest
import platform

if platform.system() == "Linux":
    from lib.testtool.osconfig.linux_config import LinuxOsConfigProfile
    from lib.testtool.osconfig.linux_controller import LinuxOsConfigController

    @pytest.fixture(scope="session", autouse=False)
    def linux_os_config():
        """Apply lab OS settings for the test session."""
        profile = LinuxOsConfigProfile.lab_default()
        controller = LinuxOsConfigController(profile=profile)
        controller.apply_all()
        yield
        controller.revert_all()
```

### 8.2 快照存放位置

| OS | 快照路徑 |
|----|---------|
| Windows | `%TEMP%\osconfig_snapshot.json` |
| Linux | `/tmp/ssd_testkit_osconfig_snapshot.json` |

---

## 九、權限需求

大部分設定需要 root：

| 動作 | 需要 root | 說明 |
|------|----------|------|
| `systemctl disable` | ✅ | 系統服務 |
| `sysctl` 寫入 | ✅ | |
| `swapoff` | ✅ | |
| CPU governor | ✅ | `/sys/devices/system/cpu/*/cpufreq/` |
| I/O scheduler | ✅ | `/sys/block/*/queue/scheduler` |
| `/etc/gdm3/custom.conf` | ✅ | |
| `gsettings`（螢幕空白） | ❌ | 需以目標使用者身份執行 |

`LinuxOsConfigController.apply_all()` 在開始前應檢查 `os.geteuid() == 0`，  
若非 root 且有需要 root 的動作，應拋出 `OsConfigPermissionError` 並提示 `sudo`。

---

## 十、實施階段

### Phase 1：基礎架構（優先）

- [ ] `lib/testtool/osconfig/linux_compat.py`（`LinuxDistroInfo`）
- [ ] `lib/testtool/osconfig/actions/linux/base_linux_action.py`（`AbstractLinuxOsAction`）
- [ ] `lib/testtool/osconfig/linux_config.py`（`LinuxOsConfigProfile`）
- [ ] `lib/testtool/osconfig/linux_controller.py`（`LinuxOsConfigController`）
- [ ] `tools/osconfig/linux/osconfig_linux.yaml`
- [ ] `tools/osconfig/linux/osconfig_linux.sh` 及四個 `.sh` 腳本

### Phase 2：核心動作（服務 + 電源）

- [ ] `UnattendedUpgradesAction`（含 apt timer）
- [ ] `ApportAction`
- [ ] `AvahiAction`
- [ ] `UfwAction`
- [ ] `CpuGovernorAction`（cpupower）
- [ ] `SuspendAction`（systemd mask）
- [ ] `SwappinessAction`
- [ ] `NmiWatchdogAction`

### Phase 3：進階動作

- [ ] `IoSchedulerAction`（NVMe）
- [ ] `HugepagesAction`（THP）
- [ ] `SwapAction`（swapoff）
- [ ] `FstrimTimerAction`
- [ ] `TrackerAction`（GNOME tracker）
- [ ] `ScreenBlankAction`（gsettings）

### Phase 4：使用者 / 開機

- [ ] `AutoLoginAction`（GDM3 / LightDM）
- [ ] `SudoNopasswdAction`
- [ ] `CoreDumpAction`
- [ ] `AppArmorAction`（謹慎）

### Phase 5：整合測試

- [ ] `tests/integration/osconfig/linux/` 各動作的整合測試
- [ ] `tools/osconfig/osconfig_tool.py` OS 路由整合

---

## 十一、風險與注意事項

| 風險 | 說明 | 對策 |
|------|------|------|
| AppArmor 影響安全性 | Ubuntu 預設啟用 | 預設設定檔不啟用 `disable_apparmor` |
| CPU governor 套件不存在 | `cpupower` 需安裝 `linux-tools-$(uname -r)` | `check()` 若工具不存在，降級為直接寫 `/sys/...` |
| gdm3 vs lightdm | Ubuntu 22.04+ 用 gdm3；部分精簡安裝用 lightdm | `AutoLoginAction` 自動偵測 |
| NVMe 裝置名稱變動 | `nvme0n1` 可能是 `nvme1n1` | `IoSchedulerAction` 掃描 `/sys/block/nvme*` 所有裝置 |
| swap 關閉後 OOM | RAM 不足時測試可能 OOM kill | `disable_swap` 預設 false，需手動啟用 |
| revert 需 root | 還原也要 root，CI pipeline 需確保 | CI 用 sudoers 設定 |
| 非 Ubuntu 差異 | CentOS 用 `firewalld` 而非 ufw；SELinux 而非 AppArmor | Phase 1 先只支援 Ubuntu，CentOS 後加 |

---

## 十二、相關檔案

| 檔案 | 類型 | 說明 |
|------|------|------|
| `lib/testtool/osconfig/` | 現有 | Windows osconfig 主目錄 |
| `tools/osconfig/osconfig.yaml` | 現有 | Windows 開發機設定（不變） |
| `tools/osconfig/linux/osconfig_linux.yaml` | 新增 | Linux 設定檔 |
| `doc/PLAN_linux_tool_support.md` | 現有 | Linux 工具支援整體計畫 |
