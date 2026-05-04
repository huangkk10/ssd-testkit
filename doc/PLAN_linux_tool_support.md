# 計畫：Linux 平台工具支援（Ubuntu / CentOS）

**版本**: v0.1  
**日期**: 2026-04-30  
**狀態**: 草稿

---

## 一、現況分析

### 1.1 現有架構（Windows）

```
[開發機 / 有完整 bin\]
  bin\installers\<ToolName>\<version>\     ← 廠商原始安裝檔 (git-ignored)
  bin\chocolatey\packages\<id>\<version>\  ← .nupkg 薄包裝腳本
        │
        │  upload_tools_to_nexus.ps1
        ▼
  [Nexus: choco-hosted-nas]               ← NuGet/Chocolatey 格式
  [NAS: windows\zip\*.zip]                ← installer 靜態備份
        │
        │  prepare_testcase.ps1
        ▼
  [新機器 / CI]
    bin\installers\ (解壓)
    bin\chocolatey\packages\ (下載 nupkg)
        │
        │  install_packages.ps1 / ChocoManager.install()
        ▼
  已安裝工具 (C:\tools\ 或 Program Files)
```

### 1.2 核心元件對照

| 元件 | 目前 Windows 實作 | 說明 |
|------|------------------|------|
| 套件格式 | `.nupkg` (NuGet/Chocolatey) | 薄包裝腳本 + nuspec |
| 套件管理器 | Chocolatey CLI | offline mode，不需 internet |
| 套件伺服器 | Nexus `choco-hosted-nas` | HTTPS API |
| 安裝檔備份 | NAS `windows\zip\*.zip` | UNC path |
| 版本設定 | `tools-registry.yaml` | 全域版本映射 |
| Python API | `ChocoManager` | 呼叫 choco CLI |
| 安裝入口 | `install_packages.ps1` / `ToolInstaller` | 讀 tools.yaml |
| 工具類型 | Type A (Installer)、Type B (Portable) | 安裝腳本分兩種 |

### 1.3 現有限制

- 所有路徑、腳本、工具類型假設 Windows（`.exe`, `.ps1`, UNC, Chocolatey）
- `tools-registry.yaml` 無 OS 欄位
- `package_meta.yaml` 無跨平台版本映射
- `ChocoManager` 直接呼叫 `choco.exe`，不抽象化

---

## 二、目標

1. **支援 Ubuntu 22.04 LTS 和 CentOS Stream 9**（優先 x86_64）
2. **工具伺服器統一分發**：同一個 Nexus 同時服務 Windows nupkg 和 Linux archive
3. **NAS 備份統一化**：按 OS 子目錄分開存放
4. **Python API 跨平台**：`ToolInstaller` / `ChocoManager` 接口不變，底層依 OS 路由

---

## 三、設計決策

### 3.1 Linux 套件策略

| 選項 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| apt/yum via Nexus | 標準、OS 原生版本管理 | Ubuntu(apt) 和 CentOS(yum) 需分開 repo 類型；廠商 binary 重新打包可能違反授權；與現有 Chocolatey 模式差距大 | 備選（未來考慮） |
| `.tar.gz` + shell install script | 結構與現有 nupkg + ps1 一一對應，移植成本低；Nexus Raw repo 一個即可服務兩種 OS | 無 OS 原生版本管理 UI | **是（主要）** |
| Ansible role | 宣告式，易 CI 整合 | 需 Ansible 環境 | 備選 |
| conda/pip only tools | 適合 Python 工具 | 只適用部份工具 | 補充 |

**決定**：以 `.tar.gz` + `install.sh` 模擬現有 Chocolatey 流程；Python 端以 `LinuxToolManager` 取代 `ChocoManager`。

### 3.2 工具伺服器選擇

現有 Nexus (`https://10.252.170.171`) 支援多種 repository 格式：

| Nexus repo 類型 | 用途 | 狀態 |
|-----------------|------|------|
| `choco-hosted-nas`（NuGet）| Windows nupkg | ✅ 已建，Phase 2 完成 |
| `raw-linux-tools-nas`（Raw）| Linux `.tar.gz` | ✅ 已建，待上傳內容 |
| `pypi-group`（PyPI）| pip 套件代理 | ✅ 已建，Phase 4 使用 |

**決定**：`raw-linux-tools-nas` 在 [packages-win-linux](https://github.com/huangkk10/packages-win-linux) Phase 1 時已建立，ssd-testkit 直接對接此 repo，不需另外建。

> **Nexus 與 NAS 的關係**：Nexus 的 blob store 實體存放在 NAS（`/mnt/nas-mdt/ssd-testkit-nexus/`），兩者並非獨立儲存，而是 Nexus 管理 NAS 上的 blob。因此「Nexus 存 thin wrapper」在實體上即是存在 NAS 的 Nexus blob 目錄內，與「NAS 存廠商 binary」的備份目錄（`ssd-testkit-source/linux/`）是不同路徑。

> **分工原則（與 Windows 一致）**：
> - **Nexus** 只存薄包裝腳本（`install.sh` + `uninstall.sh` + `metadata.yaml`），不含 binary，KB 級
> - **NAS** 存廠商 Linux binary 打成的 `.tar.gz`，MB~GB 級
> - `install.sh` 透過 `SSD_TESTKIT_ROOT` 找到 NAS 解壓後的 binary，與 Windows `chocolateyInstall.ps1` 的設計相同

### 3.3 NAS 目錄結構擴展

```
\\10.250.0.1\mdt\Team\PQ1-3\tool\ssd-testkit-source\
    windows\
        zip\          ← 廠商原始安裝檔 zip（binary，大檔）
        nupkg\        ← .nupkg 薄包裝腳本備份（無 binary）
    linux\
        ubuntu\
            tar\      ← 廠商 Ubuntu binary tar.gz（大檔）
        centos\
            tar\      ← 廠商 CentOS binary tar.gz（大檔）
```

> Nexus `raw-hosted-linux` 另外存放薄包裝腳本 tar.gz（無 binary），NAS 不重複存這部分。

---

## 四、架構變更

### 4.1 `tools-registry.yaml` 新增 OS 區分

```yaml
# 現有（保持向下相容）
tools:
  smicli:
    version: 2026.2.13
    source_dir: bin/installers/SmiCli/v20260213C
    nexus_path: windows-tools/SmiCli/v20260213C/SmiCli-v20260213C.zip
    install_dir: C:\\tools\\SmiCli
    env_var: SMICLI_PATH
    binaries: [SmiCli2.exe]

# 新增（跨平台工具範例）
tools:
  smicli:
    windows:
      version: 2026.2.13
      source_dir: bin/installers/SmiCli/v20260213C
      nexus_path: windows-tools/SmiCli/v20260213C/SmiCli-v20260213C.zip
      install_dir: C:\\tools\\SmiCli
      env_var: SMICLI_PATH
      binaries: [SmiCli2.exe]
    ubuntu:
      version: 2026.2.13
      source_dir: bin/installers/SmiCli/linux/v20260213C
      nexus_path: linux/ubuntu/SmiCli/v20260213C/SmiCli-v20260213C-ubuntu.tar.gz
      install_dir: /opt/smicli
      env_var: SMICLI_PATH
      binaries: [smicli]
    centos:
      version: 2026.2.13
      source_dir: bin/installers/SmiCli/linux/v20260213C
      nexus_path: linux/centos/SmiCli/v20260213C/SmiCli-v20260213C-centos.tar.gz
      install_dir: /opt/smicli
      env_var: SMICLI_PATH
      binaries: [smicli]
```

> **向下相容原則**：若 `tools-registry.yaml` 中某工具為平坦格式（無 OS 子鍵），視為 Windows-only。

### 4.2 `package_meta.yaml` 新增 linux 版本段

```yaml
tool_name: smicli
choco_package_id: smicli        # Windows 用
tool_type: portable

versions:
  - version: "2026.2.13"
    tool_version: "v20260213C"
    source_dir: "bin/installers/SmiCli/v20260213C"
    default: true

linux_versions:                 # 新增
  - version: "2026.2.13"
    tool_version: "v20260213C"
    ubuntu_source_dir: "bin/installers/SmiCli/linux/v20260213C"
    centos_source_dir: "bin/installers/SmiCli/linux/v20260213C"
    default: true
```

### 4.3 Linux 套件結構（對應 nupkg，Nexus 存放內容）

> 此結構打包成 `.tar.gz` 上傳至 Nexus，**不含任何廠商 binary**。
> 廠商 binary 另外打包存 NAS（見 3.3）。

```
bin/linux-packages/<tool-id>/<version>/
    install.sh        ← 安裝腳本（類比 chocolateyInstall.ps1）
    uninstall.sh      ← 移除腳本
    metadata.yaml     ← 類比 nuspec
```

**`metadata.yaml` 範例**：
```yaml
id: smicli
version: "2026.2.13"
tool_version: "v20260213C"
description: SMI CLI tool for SSD testing
platforms: [ubuntu, centos]
install_dir: /opt/smicli
env_var: SMICLI_PATH
binaries: [smicli]
```

**`install.sh` 範例（Portable 類型）**：
```bash
#!/usr/bin/env bash
set -euo pipefail

TOOL_VERSION="v20260213C"
INSTALL_DIR="/opt/smicli"
TOOLKIT_ROOT="${SSD_TESTKIT_ROOT:?SSD_TESTKIT_ROOT is not set}"

SOURCE_DIR="${TOOLKIT_ROOT}/bin/installers/SmiCli/linux/${TOOL_VERSION}"
if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "ERROR: Source not found: ${SOURCE_DIR}" >&2
    exit 1
fi

mkdir -p "${INSTALL_DIR}"
cp -r "${SOURCE_DIR}/." "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/smicli"

# 寫入 /etc/environment.d/ 或 /etc/profile.d/
cat > /etc/profile.d/smicli.sh << 'EOF'
export SMICLI_PATH=/opt/smicli
export PATH="$PATH:/opt/smicli"
EOF

echo "Installed smicli ${TOOL_VERSION} to ${INSTALL_DIR}"
```

### 4.4 Python 端架構重構

```
lib/testtool/
    tool_manager.py          ← 新增：統一入口，依 OS 路由
    choco_manager.py         ← 現有，Windows 不變
    linux_tool_manager.py    ← 新增：Linux 安裝邏輯
    tool_installer.py        ← 現有，擴展讀取 OS 段
```

**`tool_manager.py`（新增，OS 路由層）**：
```python
import platform
from lib.testtool.choco_manager import ChocoManager
from lib.testtool.linux_tool_manager import LinuxToolManager

def get_tool_manager():
    os_name = platform.system().lower()
    if os_name == "windows":
        return ChocoManager()
    elif os_name == "linux":
        return LinuxToolManager()
    else:
        raise RuntimeError(f"Unsupported OS: {os_name}")
```

**`LinuxToolManager`（新增）**：
- 讀取 `package_meta.yaml` 的 `linux_versions` 段
- 呼叫 `install.sh` / `uninstall.sh`
- `is_installed()` 以 binary 存在與否判斷
- 介面與 `ChocoManager` 一致（`install()`, `uninstall()`, `is_installed()`）

---

## 五、流程變更

### 5.1 打包流程（新增 Linux）

```
開發機（有完整 bin/installers/）
    │
    ├─ Windows：choco pack → .nupkg → upload_tools_to_nexus.ps1
    │
    └─ Linux：  bash pack_linux.sh → .tar.gz → upload_tools_to_nexus.sh
                                              (curl PUT 到 raw-hosted-linux)
```

**新增腳本**：
- `tool-manager/pack_linux.sh`：打包 `bin/linux-packages/<id>/<version>/`（腳本層）為 thin wrapper tar.gz
- `tool-manager/upload_tools_linux.sh`：
  - **Part 1**：thin wrapper tar.gz → POST 到 Nexus `raw-hosted-linux`
  - **Part 2**：`bin/installers/<source_dir>/` → Compress → Copy 到 NAS `linux/ubuntu/tar/` 或 `linux/centos/tar/`

### 5.2 準備流程（新增 Linux）

```bash
# 新機器（Ubuntu/CentOS）
./tool-manager/prepare_testcase.sh stc1685_burnin

# 動作：
# 1. 讀 tools.yaml、tools-registry.yaml（linux 段）
# 2. 從 Nexus raw-hosted-linux 下載 .tar.gz（若不存在）
# 3. 從 NAS linux/ubuntu/tar/ 複製 installer tar.gz（若不存在）
# 4. 解壓到 bin/installers/
```

### 5.3 安裝流程（新增 Linux）

```
ToolInstaller.install_all()
    → get_tool_manager()      ← OS 路由
    → LinuxToolManager.install("smicli")
        → 讀 package_meta.yaml linux_versions
        → 執行 install.sh (sudo)
        → 確認 binary 存在
```

### 5.4 開發機打包上傳流程（Windows vs Linux 對照）

新增一個工具的 Linux 支援時，開發機需執行以下步驟（對應 Windows 的 `choco pack` + `upload_tools_to_nexus.ps1`）：

| 步驟 | Windows（現有） | Linux（新增） |
|------|----------------|--------------|
| 1. 準備安裝檔 | 廠商提供 `.exe` / `.zip` → 放入 `bin\installers\<ToolName>\<ver>\` | 廠商提供 Linux binary → 放入 `bin/installers/<ToolName>/linux/<ver>/` |
| 2. 撰寫安裝腳本 | `bin\chocolatey\packages\<id>\<ver>\chocolateyInstall.ps1` | `bin/linux-packages/<id>/<ver>/install.sh` + `uninstall.sh` + `metadata.yaml` |
| 3. 打包腳本層 | `choco pack` → `<id>.<ver>.nupkg` | `bash tool-manager/pack_linux.sh <id> <ver>` → `<id>-<ver>-linux.tar.gz` |
| 4. 上傳腳本至 Nexus | `upload_tools_to_nexus.ps1` → `choco-hosted-nas` | `bash tool-manager/upload_tools_linux.sh <id> <ver>` Part 1 → `raw-linux-tools-nas` |
| 5. 備份 binary 至 NAS | 手動複製 installer zip → NAS `windows/zip/` | `upload_tools_linux.sh` Part 2 → NAS `linux/ubuntu/tar/` 及 `linux/centos/tar/` |

#### `pack_linux.sh` 執行內容

```bash
# 用法
bash tool-manager/pack_linux.sh smicli 2026.2.13

# 動作：
# 1. 進入 bin/linux-packages/smicli/2026.2.13/
# 2. 確認 install.sh、uninstall.sh、metadata.yaml 都存在
# 3. 打包為 smicli-2026.2.13-linux.tar.gz
```

#### `upload_tools_linux.sh` 執行內容

```bash
# 用法
bash tool-manager/upload_tools_linux.sh smicli 2026.2.13

# Part 1：上傳 thin wrapper 至 Nexus（KB 級，只含腳本）
curl -sk --ssl-no-revoke --noproxy "10.252.170.171" \
    -u "admin:1.a" \
    --upload-file "smicli-2026.2.13-linux.tar.gz" \
    "https://10.252.170.171/repository/raw-linux-tools-nas/smicli/2026.2.13/smicli-2026.2.13-linux.tar.gz"

# Part 2：壓縮廠商 binary 並複製至 NAS（MB~GB 級）
#   讀 bin/linux-packages/smicli/2026.2.13/metadata.yaml 取得 source_dir
#   tar -czf SmiCli-v20260213C-ubuntu.tar.gz -C bin/installers/SmiCli/linux/v20260213C .
#   cp SmiCli-v20260213C-ubuntu.tar.gz /mnt/nas-mdt/.../linux/ubuntu/tar/
#   cp SmiCli-v20260213C-centos.tar.gz /mnt/nas-mdt/.../linux/centos/tar/  （若有 CentOS 版）
```

> **前提**：執行 Part 2 時開發機需已掛載 NAS（`sudo mount -t cifs //10.250.0.1/mdt /mnt/nas-mdt ...`）。若只需更新腳本邏輯（不換 binary），可只執行 Part 1。

#### 完整新增工具流程示意

```
開發機（有 NAS 存取權）
  │
  ├─ 1. 取得廠商 Linux binary，放入 bin/installers/SmiCli/linux/v20260213C/
  │
  ├─ 2. 撰寫 bin/linux-packages/smicli/2026.2.13/
  │         install.sh、uninstall.sh、metadata.yaml
  │
  ├─ 3. bash tool-manager/pack_linux.sh smicli 2026.2.13
  │         → smicli-2026.2.13-linux.tar.gz
  │
  ├─ 4. bash tool-manager/upload_tools_linux.sh smicli 2026.2.13
  │         → Part 1: thin wrapper → Nexus raw-linux-tools-nas
  │         → Part 2: binary tar.gz → NAS linux/ubuntu/tar/
  │
  └─ 5. 更新 lib/testtool/tools-registry.yaml（加 ubuntu/centos 子鍵）
         更新 bin/chocolatey/packages/smicli/.../package_meta.yaml（加 linux_versions）
```

---

## 六、Nexus 設定變更

### 6.1 Raw repository（已存在）

| 設定 | 值 |
|------|---|
| 類型 | `raw (hosted)` |
| Name | `raw-linux-tools-nas` |
| Blob Store | `nas-blob`（實體在 NAS `/mnt/nas-mdt/ssd-testkit-nexus/`） |
| URL | `https://10.252.170.171/repository/raw-linux-tools-nas/` |

> 此 repo 由 [packages-win-linux](https://github.com/huangkk10/packages-win-linux) Phase 1 建立完成，ssd-testkit 無需重建，直接上傳套件即可。

### 6.2 上傳 / 下載指令

#### Nexus：thin wrapper（install.sh + metadata，無 binary）

```bash
# 上傳 thin wrapper（開發機）
curl -sk --ssl-no-revoke --noproxy "10.252.170.171" \
    -u "admin:1.a" \
    --upload-file "smicli-2026.2.13-linux.tar.gz" \
    "https://10.252.170.171/repository/raw-linux-tools-nas/smicli/2026.2.13/smicli-2026.2.13-linux.tar.gz"

# 下載 thin wrapper（新機器）
curl -sk --ssl-no-revoke --noproxy "10.252.170.171" \
    -u "admin:1.a" \
    -o "smicli-2026.2.13-linux.tar.gz" \
    "https://10.252.170.171/repository/raw-linux-tools-nas/smicli/2026.2.13/smicli-2026.2.13-linux.tar.gz"
```

#### NAS：廠商 binary（由 install.sh 在安裝時取用）

```bash
# 複製 binary tar.gz 到 NAS（開發機，Linux mount SMB）
cp "SmiCli-v20260213C-ubuntu.tar.gz" \
    "/mnt/nas/Team/PQ1-3/tool/ssd-testkit-source/linux/ubuntu/tar/"

# prepare_testcase.sh 從 NAS 複製並解壓
cp "/mnt/nas/.../linux/ubuntu/tar/SmiCli-v20260213C-ubuntu.tar.gz" .
tar -xzf "SmiCli-v20260213C-ubuntu.tar.gz" -C "bin/installers/SmiCli/linux/"
```

---

## 七、工具分類：Linux 支援優先順序

| 工具 | Windows 類型 | Linux 可行性 | 說明 |
|------|-------------|-------------|------|
| `smicli` | Portable | 高（若有 Linux binary） | 先確認廠商是否提供 Linux 版 |
| `smiwintools` | Portable | 中 | 名稱含 Win，需確認 |
| `burnin` | Installer | 低（GUI 工具） | 可能無 Linux 版 |
| `cdi` | Installer | 低（Windows GUI） | 無 Linux 版 |
| `phm` | Installer | 待確認 | 需與廠商確認 |
| `windows-adk` | Installer | 不適用 | Windows 專屬 |
| `python_installer` | Installer | 改用系統 python3 | Ubuntu/CentOS 直接 apt/yum |
| `net_7_sdk` | Installer | 高（官方支援 Linux） | dotnet-sdk-7 apt/yum 可取得 |

---

## 八、實施階段

### Phase 1 — 基礎設施（0.5 週，大部分已就緒）
- [x] Nexus `raw-linux-tools-nas` repository 已建立（packages-win-linux Phase 1）
- [x] Nexus NAS blob store 已掛載（`/mnt/nas-mdt/ssd-testkit-nexus/`）
- [ ] NAS 建立 `ssd-testkit-source/linux/ubuntu/tar/` 和 `linux/centos/tar/` 備份目錄
- [ ] `tools-registry.yaml` 格式擴展（加 OS 子鍵），保持向下相容
- [ ] `prepare_testcase.sh`（Linux 版本）

### Phase 2 — Python 抽象層（1.5 週）
- [ ] 新增 `lib/testtool/linux_tool_manager.py`
- [ ] 新增 `lib/testtool/tool_manager.py`（OS 路由）
- [ ] `ToolInstaller` 擴展：讀取 `linux_versions`，呼叫 `get_tool_manager()`
- [ ] 單元測試：mock `platform.system()`

### Phase 3 — 第一個工具移植（1 週）
- [ ] 選定一個 Linux 可用工具（建議 `smicli` 或 `net_7_sdk`）
- [ ] 建立 `bin/linux-packages/<id>/<version>/install.sh`
- [ ] 打包、上傳至 Nexus + NAS
- [ ] `package_meta.yaml` 新增 `linux_versions`
- [ ] Integration test 驗證（Ubuntu 22.04 VM）

### Phase 4 — CI 整合與 Python 依賴（1 週）
- [ ] CI pipeline 偵測執行環境，選擇對應 `prepare_testcase.bat` / `.sh`
- [ ] 補齊其他工具的 Linux 移植（依 Phase 3 模板）
- [ ] Linux 機器的 pip 指向 Nexus `pypi-group`（對接 packages-win-linux Phase 4）
- [ ] 更新 `prepare_testcase.sh` 或 `bootstrap.sh` 自動設定 `pip.conf`

> **與 packages-win-linux 的協作**：Phase 4 的 Python 依賴統一由 packages-win-linux Phase 4 負責設定 PyPI proxy，ssd-testkit 側只需在 bootstrap 時寫入 `pip.conf`。

---

## 九、風險與注意事項

| 風險 | 影響 | 緩解 |
|------|------|------|
| 廠商工具無 Linux 版本 | 高 | 提前確認，使用 Wine 或替代工具 |
| `sudo` 權限需求 | 中 | install.sh 說明，或改安裝到 `$HOME/.local/` |
| NAS UNC path Linux 掛載 | 中 | 改用 SMB/CIFS `mount`，或 rsync over SSH |
| Nexus TLS 憑證在 Linux curl | 低 | 加 `--ssl-no-revoke` 同 Windows 處理方式 |
| 版本號格式差異 | 低 | `package_meta.yaml` 分開記錄 `tool_version` |

---

## 十、Linux 主機端從零到工具就緒

### 10.0 前置條件

| 項目 | 說明 |
|------|------|
| Python 3.10+ | `sudo apt install python3 python3-pip` / `sudo yum install python3` |
| git | `sudo apt install git` / `sudo yum install git` |
| cifs-utils（SMB 掛載） | `sudo apt install cifs-utils` / `sudo yum install cifs-utils` |
| Nexus 網路 | 可連 `https://10.252.170.171`（若有 self-signed 憑證，需匯入 CA） |
| NAS 網路 | 可連 `\\10.250.0.1\mdt`（SMB） |
| sudo 權限 | install.sh 安裝到 `/opt/` 需要 sudo（CI 建議設 NOPASSWD） |

---

### 10.1 步驟一：Clone 專案並設定環境變數

```bash
git clone https://github.com/huangkk10/ssd-testkit.git
cd ssd-testkit

# 設定 SSD_TESTKIT_ROOT（install.sh 靠此找 bin/installers/）
export SSD_TESTKIT_ROOT="$(pwd)"

# 建議寫入 ~/.bashrc 或 /etc/environment 讓每次登入自動生效
echo "export SSD_TESTKIT_ROOT=$(pwd)" >> ~/.bashrc

# Python 依賴
pip3 install -r requirements.txt \
    --index-url https://10.252.170.171/repository/pypi-group/simple/ \
    --trusted-host 10.252.170.171
```

---

### 10.2 步驟二：掛載 NAS（對應 Windows `net use`）

```bash
# 建立掛載點
sudo mkdir -p /mnt/nas-mdt

# 手動掛載（測試用）
sudo mount -t cifs //10.250.0.1/mdt /mnt/nas-mdt \
    -o username=mdt,password=p@ssw0rd,dir_mode=0755,file_mode=0644,vers=3.0

# 開機自動掛載（/etc/fstab）
echo "//10.250.0.1/mdt  /mnt/nas-mdt  cifs  username=mdt,password=p@ssw0rd,dir_mode=0755,file_mode=0644,vers=3.0,_netdev  0 0" \
    | sudo tee -a /etc/fstab
```

> `prepare_testcase.sh` 會在腳本開頭自動嘗試掛載，失敗時顯示 `[WARN]`（同 Windows 的 `net use` 邏輯）。

---

### 10.3 步驟三：準備工具（對應 Windows `prepare_testcase.bat`）

```bash
# 指定 testcase
./tool-manager/prepare_testcase.sh stc1685_burnin

# 或使用 prepare.yaml
./tool-manager/prepare_testcase.sh
```

**腳本執行內容**（與 Windows 版本對應）：

| Step | Windows | Linux |
|------|---------|-------|
| 1 | Nexus `choco-hosted-nas` 下載 `.nupkg` | Nexus `raw-linux-tools-nas` 下載 thin wrapper `.tar.gz` |
| 2 | NAS `windows/zip/` 複製 installer zip 解壓 | NAS `linux/ubuntu/tar/` 或 `linux/centos/tar/` 複製 binary tar.gz 解壓 |

**輸出範例**：
```
TestCase: stc1685_burnin
  [NAS] Mounting //10.250.0.1/mdt → /mnt/nas-mdt ...
  [DOWNLOAD] smicli 2026.2.13        ← 從 Nexus raw-linux-tools-nas 下載 thin wrapper
  [COPY] installer smicli  /mnt/nas-mdt/.../linux/ubuntu/tar/SmiCli-v20260213C-ubuntu.tar.gz
  [SKIP] installer cdi (not available on linux — skipping)
Tools ready: stc1685_burnin
```

---

### 10.4 步驟四：執行 pytest，自動安裝工具

```bash
cd ssd-testkit
sudo -E python3 -m pytest tests/integration/test_case/stc1685_burnin/ -v
# -E：保留 SSD_TESTKIT_ROOT 等環境變數給 sudo 環境
```

pytest 執行時，`ToolInstaller` 在 `setup_test_class` / `test_01_precondition` 中呼叫 `LinuxToolManager.install()`：

```
pytest
  └─ ToolInstaller.install_pre_runcard()
       └─ LinuxToolManager.install("smicli")
            → sudo bash bin/linux-packages/smicli/2026.2.13/install.sh
            → 從 bin/installers/SmiCli/linux/v20260213C/ 複製到 /opt/smicli/
            → _inject_env_from_meta("smicli")  → os.environ["SMICLI_PATH"] = "/opt/smicli"
```

---

### 10.5 對應關係總覽（Windows vs Linux）

```
Windows                              Linux
─────────────────────────────────────────────────────────────
net use \\NAS\mdt                    mount -t cifs //NAS/mdt /mnt/nas-mdt
prepare_testcase.bat                 prepare_testcase.sh
  ↓ Nexus choco-hosted-nas           ↓ Nexus raw-linux-tools-nas
  ↓ NAS windows/zip/                 ↓ NAS linux/ubuntu/tar/ (or centos)
  ↓ .nupkg → bin/chocolatey/        ↓ .tar.gz → bin/linux-packages/
  ↓ installer zip → bin/installers/ ↓ binary tar.gz → bin/installers/

bootstrap.ps1 / install_packages.ps1  pytest → ToolInstaller
  ↓ choco install <id>               ↓ LinuxToolManager.install(<id>)
  ↓ chocolateyInstall.ps1            ↓ sudo bash install.sh
  ↓ 寫入 registry env var            ↓ 寫入 /etc/profile.d/
  ↓ _inject_env_from_meta()          ↓ _inject_env_from_meta()  ← 相同邏輯
  ↓ C:\tools\<tool>\                 ↓ /opt/<tool>/
```

---

## 十一、Linux Testcase 安裝工具流程（Python 層）

### 11.1 現有 Windows 運作方式（回顧）

Linux testcase 的設計目標是讓 `tools.yaml` 格式**完全不變**，只有底層路由邏輯依 OS 切換。

目前 Windows 流程：
```
tests/integration/test_case/<name>/Config/tools.yaml
    ↓  ToolInstaller._load()
ToolEntry(id, reinstall, version, phase, env)
    ↓  ToolInstaller._install()
ChocoManager.install(id, version)   ← 直接呼叫 choco.exe
```

### 11.2 Linux Testcase 流程（目標）

```
tests/integration/test_case/<name>/Config/tools.yaml   ← 格式不變
    ↓  ToolInstaller._load()                            ← 不變
ToolEntry(id, reinstall, version, phase, env)
    ↓  ToolInstaller._install()
get_tool_manager()          ← 依 platform.system() 路由
    ↓  (Linux)
LinuxToolManager.install(id, version)
    → 讀 package_meta.yaml linux_versions 段
    → 執行 bin/linux-packages/<id>/<version>/install.sh (sudo)
    → 確認 binary 存在
```

### 11.3 tools.yaml 不需要修改

Linux testcase 的 `tools.yaml` 語法與 Windows **完全相同**，不需要加 OS 欄位：

```yaml
# tests/integration/test_case/stcXXXX_linux_nvme/Config/tools.yaml
tools:
  - id: smicli
    reinstall: false
    phase: pre_runcard   # 與 Windows 語義相同

  - id: diskercise
    reinstall: false
```

OS 差異完全封裝在 `LinuxToolManager` 內部，testcase 開發者不需要感知。

> **例外**：若某工具只有 Windows 版本（如 `windows-adk`），`LinuxToolManager` 應在 `install()` 時拋出明確的 `ToolNotSupportedOnPlatform` 例外，而非靜默跳過。

### 11.4 install.sh 執行機制

`LinuxToolManager.install()` 執行流程：

```python
# lib/testtool/linux_tool_manager.py（示意）
def install(self, tool_id: str, version: str | None = None) -> InstallResult:
    meta = self._load_meta(tool_id)           # 讀 package_meta.yaml linux_versions
    pkg_dir = self._resolve_pkg_dir(tool_id, version)  # bin/linux-packages/<id>/<ver>/
    install_sh = pkg_dir / "install.sh"

    env = os.environ.copy()
    env["SSD_TESTKIT_ROOT"] = str(self._root)

    result = subprocess.run(
        ["sudo", "bash", str(install_sh)],
        env=env, capture_output=True, text=True
    )
    return InstallResult(
        success=(result.returncode == 0),
        tool_id=tool_id,
        version=version or meta["default_version"],
        exit_code=result.returncode,
        output=result.stdout + result.stderr,
    )

def is_installed(self, tool_id: str) -> bool:
    meta = self._load_meta(tool_id)
    install_dir = Path(meta["install_dir"])
    binary = meta["binaries"][0]
    return (install_dir / binary).exists()
```

### 11.5 sudo 權限處理策略

install.sh 安裝到 `/opt/` 需要 sudo，有三種策略：

| 策略 | 說明 | 建議場景 |
|------|------|---------|
| `sudo bash install.sh` | 直接 sudo，需 CI runner 有 NOPASSWD | CI 環境（標準做法） |
| install.sh 安裝到 `$HOME/.local/` | 不需 sudo，但 env var 只對當前使用者 | 受限環境 |
| 以 root 執行整個 testcase | 整個 pytest 以 root 跑 | 不建議（安全風險） |

**建議**：CI runner 設定 `NOPASSWD: /usr/bin/bash`，install.sh 只安裝到 `/opt/` 不做系統層修改。

### 11.6 env var 注入（對應 Windows registry 行為）

Windows 的 `chocolateyInstall.ps1` 會寫入機器層 registry，Python 端靠 `_inject_env_from_meta()` 補注入。
Linux 的 `install.sh` 寫入 `/etc/profile.d/`，但當前 process 仍看不到，同樣需要 Python 端注入：

```python
# ToolInstaller._install() 在呼叫 install() 之後，現有邏輯不變
self._inject_env_from_meta(entry.id)   # 讀 install_dir + env_var，寫入 os.environ
for var, val in entry.env.items():
    os.environ[var] = val              # tools.yaml 顯式覆蓋
```

`_inject_env_from_meta()` 讀取 `package_meta.yaml` 的 `install_dir` 和 `env_var`，Linux 上路徑為 `/opt/smicli`，邏輯相同，不需要修改。

### 11.7 prepare_testcase.sh 與安裝的責任邊界

與 Windows 相同，**prepare 不負責安裝**：

| 步驟 | 腳本 | 動作 |
|------|------|------|
| 1 | `prepare_testcase.sh` | 從 Nexus 下載薄包裝 tar.gz → `bin/linux-packages/` |
| 2 | `prepare_testcase.sh` | 從 NAS 複製廠商 binary tar.gz → 解壓到 `bin/installers/` |
| 3 | `ToolInstaller.install_all()` | 執行 `install.sh`，把 binary 複製到 `/opt/<tool>` |

---

## 十一、相關檔案與外部 Repo

### ssd-testkit（本 repo）

| 檔案 | 說明 |
|------|------|
| `lib/testtool/tools-registry.yaml` | 工具版本主設定（需擴展 OS 子鍵） |
| `lib/testtool/choco_manager.py` | 現有 Windows 安裝 API |
| `lib/testtool/tool_installer.py` | 安裝入口（需擴展 OS 路由） |
| `tool-manager/prepare_testcase.ps1` | Windows 準備腳本（Linux `.sh` 版本參考範本） |
| `tool-manager/upload_tools_to_nexus.ps1` | Windows 上傳腳本（Linux `.sh` 版本參考範本） |
| `bin/chocolatey/packages/` | Windows nupkg 結構可參考設計 Linux packages |

### packages-win-linux（Nexus 管理 repo）

| 項目 | 說明 |
|------|------|
| [packages-win-linux](https://github.com/huangkk10/packages-win-linux) | Nexus 伺服器部署與套件上傳管理 |
| `docs/PLAN.md` | Nexus 整體建置計畫（Phase 3 Linux 為本計畫對接點） |
| `scripts/upload/upload_nupkg.sh` | Windows nupkg 上傳腳本（Linux raw 上傳腳本參考範本） |
| `nexus/docker/` | Nexus Docker Compose 設定 |
| Nexus URL | `https://10.252.170.171`（`nexus.internal`） |
| `raw-linux-tools-nas` repo | Linux thin wrapper 上傳目標（已建好） |

---

## 十二、免 clone 單機安裝：ssd-tool CLI（方向 B）

### 12.1 動機與對比

現有 pytest 流程（方向 A）需要先 clone repo，才能執行 `prepare_testcase.sh` 和 pytest。對於只需要快速安裝單一工具的場景（如新機器驗收、臨時測試），可設計一個 `ssd-tool` CLI，對應 Windows 上的 `choco install`，**不需要 clone repo**。

| | pytest 流程（方向 A，主要） | ssd-tool CLI（方向 B） |
|--|--|--|
| 需要 clone repo | 是 | 否 |
| 使用場景 | CI / 完整 testcase 執行 | 快速單機安裝一個工具 |
| `install.sh` 取 binary | 讀 `$SSD_TESTKIT_ROOT/bin/installers/`（prepare 已預備好） | `install.sh` 自己連 NAS 下載 |
| ssd-tool 本體來自 | repo 內 `tool-manager/` | Nexus `raw-linux-tools-nas/bootstrap/` |

---

### 12.2 使用方式

```bash
# Step 1：安裝 ssd-tool CLI（類比安裝 choco 本身，一次性）
curl -sk --ssl-no-revoke --noproxy "10.252.170.171" \
    "https://10.252.170.171/repository/raw-linux-tools-nas/bootstrap/ssd-tool-install.sh" \
    | sudo bash

# Step 2：安裝指定工具（類比 choco install，之後可重複使用）
ssd-tool install smicli 2026.2.13
```

對比 Windows：
```powershell
# Windows（類比）
choco install smicli --version 2026.2.13
```

---

### 12.3 架構設計

```
Nexus raw-linux-tools-nas
    ├─ bootstrap/
    │      ssd-tool-install.sh    ← Step 1 下載安裝 ssd-tool CLI 本體
    │      ssd-tool               ← ssd-tool CLI（shell script）
    └─ smicli/2026.2.13/
           install.sh             ← thin wrapper（含 NAS 取檔邏輯，standalone 模式）
           metadata.yaml

NAS linux/ubuntu/tar/
    └─ SmiCli-v20260213C-ubuntu.tar.gz   ← 廠商 binary（ssd-tool install 時自行取得）
```

**`ssd-tool install smicli 2026.2.13` 執行流程**：
1. 從 Nexus 下載 `smicli/2026.2.13/` thin wrapper tar.gz 到 `/tmp/`
2. 解壓，以 `STANDALONE=true` 執行 `install.sh`
3. `install.sh` 用 `smbclient` 從 NAS 下載 binary tar.gz 到 `/tmp/`
4. 解壓 binary，複製到 `/opt/smicli/`
5. 寫入 `/etc/profile.d/smicli.sh`

---

### 12.4 install.sh 的兩種模式

方向 B 的 `install.sh` 以環境變數 `STANDALONE` 區分兩種模式，共用安裝邏輯：

```bash
#!/usr/bin/env bash
set -euo pipefail

TOOL_VERSION="v20260213C"
INSTALL_DIR="/opt/smicli"
STANDALONE="${STANDALONE:-false}"        # false = pytest 流程；true = ssd-tool 流程
NAS_UNC="${NAS_UNC:-//10.250.0.1/mdt}"  # standalone 模式用

if [[ "${STANDALONE}" == "true" ]]; then
    # 方向 B：自己從 NAS 下載 binary（不依賴 SSD_TESTKIT_ROOT）
    BINARY_TAR="/tmp/SmiCli-${TOOL_VERSION}-ubuntu.tar.gz"
    smbclient "${NAS_UNC}" -U "mdt%${NAS_PASS:?NAS_PASS is not set}" \
        -c "get Team/PQ1-3/tool/ssd-testkit-source/linux/ubuntu/tar/SmiCli-${TOOL_VERSION}-ubuntu.tar.gz ${BINARY_TAR}"
    mkdir -p "/tmp/smicli-src"
    tar -xzf "${BINARY_TAR}" -C "/tmp/smicli-src/"
    SOURCE_DIR="/tmp/smicli-src"
else
    # 方向 A：從 SSD_TESTKIT_ROOT 取 prepare 已預備的 binary
    TOOLKIT_ROOT="${SSD_TESTKIT_ROOT:?SSD_TESTKIT_ROOT is not set}"
    SOURCE_DIR="${TOOLKIT_ROOT}/bin/installers/SmiCli/linux/${TOOL_VERSION}"
fi

# 安裝（兩種模式共用）
if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "ERROR: Source not found: ${SOURCE_DIR}" >&2; exit 1
fi
mkdir -p "${INSTALL_DIR}"
cp -r "${SOURCE_DIR}/." "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/smicli"

cat > /etc/profile.d/smicli.sh << 'EOF'
export SMICLI_PATH=/opt/smicli
export PATH="$PATH:/opt/smicli"
EOF

echo "Installed smicli ${TOOL_VERSION} to ${INSTALL_DIR}"
```

---

### 12.5 實施條件與限制

| 項目 | 說明 |
|------|------|
| 前置依賴 | `smbclient`（`sudo apt install samba-client` / `sudo yum install samba-client`） |
| NAS 帳密 | 透過環境變數 `NAS_PASS` 傳入，不可 hardcode |
| Nexus 網路 | 可連 `https://10.252.170.171` |
| 適用場景 | 快速驗收新機器、臨時安裝單一工具 |
| 不適用場景 | CI 完整 testcase 執行（仍建議方向 A pytest 流程） |

> **安全提醒**：`curl | bash` 模式建議僅限受信任的內網環境使用，或先下載腳本確認內容後再執行。

---

### 12.6 實施優先順序

方向 B 為**選擇性功能**，不在 Phase 1–3 的必要路徑上。建議 Phase 3 驗證第一個工具的 pytest 流程（方向 A）完成後，再評估是否實作 `ssd-tool` CLI。
