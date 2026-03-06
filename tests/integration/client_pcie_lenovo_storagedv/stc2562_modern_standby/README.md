# STC-2562: Modern Standby Integration Test

## 概述 (Overview)

對 SSD 執行 PHM (Powerhouse Mountain) toolchain 進行 Windows Modern Standby (ACPI S0ix) 測試，
驗證 SSD 在睡眠/喚醒循環後的健康狀態。

## 測試流程 (Test Flow)

測試分為兩個 Phase，中間以系統重開機分隔。

### Phase A — Pre-Reboot (步驟 01–08)

| 步驟 | 說明 |
|---|---|
| 01 | **Precondition** — 建立 log 目錄 |
| 02 | **CDI Before** — 取 SMART baseline (`Before_` prefix) |
| 03 | **Install PHM** — 靜默安裝 Powerhouse Mountain |
| 04 | **PEPChecker** — 執行 PEPChecker.exe，收集 4 個輸出檔案到 `testlog/PEPChecker_Log/` |
| 05 | **PwrTest** — 睡眠/喚醒循環 + 收集 sleepstudy HTML |
| 06 | **Verify Sleepstudy** — SW DRIPS ≥ 90% 且 HW DRIPS ≥ 90% |
| 07 | **OsConfig** — 停用 Search Index、OneDrive、Windows Defender |
| 08 | **Reboot** — 排程重開機，寫入 reboot state file |

### Phase B — Post-Reboot (步驟 09–11)

| 步驟 | 說明 |
|---|---|
| 09 | **PHM Web** — 啟動 PHM，驗證 `http://localhost:1337` 回應 HTTP 200 |
| 10 | **CDI After** — 取 SMART 快照 (`After_` prefix) |
| 11 | **SMART Compare** — Unsafe Shutdowns 不能增加；錯誤計數必須為 0 |

## 目錄結構 (Directory Structure)

```
stc2562_modern_standby/
├── __init__.py
├── conftest.py              # testcase_config fixture
├── test_main.py             # 主測試檔 (TestSTC2562ModernStandby)
├── README.md                # 本文件
└── Config/
    └── Config.json          # 主設定檔
```

## 前置需求 (Prerequisites)

| 項目 | 說明 |
|---|---|
| 執行權限 | **系統管理員** (Administrator) |
| PHM 安裝檔 | `bin/PHM/phm_nda_V4.22.0_B25.02.06.02_H.exe` |
| CrystalDiskInfo | `bin/CrystalDiskInfo/DiskInfo64.exe` |
| PwrTest | `bin/PwrTest/pwrtest.exe` |
| PEPChecker | 由 PHM 安裝後位於預設路徑 (`C:\Program Files\PowerhouseMountain\NDA\...`) |
| Modern Standby | 系統須支援 ACPI S0ix (Windows Modern Standby) |

## 執行測試 (Run Test)

### 完整測試（開發環境）

```powershell
cd C:\automation\ssd-testkit
pytest tests\integration\client_pcie_lenovo_storagedv\stc2562_modern_standby\test_main.py -v -s
```

### 使用 RunTest.exe（正式封裝版）

```powershell
cd STC-2562_ModernStandby_<date>
.\RunTest.exe --test tests\integration\client_pcie_lenovo_storagedv\stc2562_modern_standby\test_main.py -v
```

### 僅執行特定步驟（跳過重開機）

```powershell
# Phase A only
pytest test_main.py -v -s -k "01 or 02 or 03 or 04 or 05 or 06 or 07"

# Phase B only (post-reboot simulation)
pytest test_main.py -v -s -k "09 or 10 or 11"
```

## Reboot Resume 機制

1. **步驟 08** 呼叫 `OsRebootController`，寫入 `testlog/reboot_state.json`（`is_recovering: true`）並排程 Windows 重開機。
2. 系統重開機後，`RunTest.exe` / `run_test.py` 重新啟動 pytest session。
3. pytest 重新執行整個 test class，但各步驟會用 `OsRebootStateManager.is_recovering()` 偵測 phase：
   - **步驟 01–08**：偵測到 `is_recovering=true` 時 `pytest.skip`
   - **步驟 09–11**：偵測到 `is_recovering=false` 時 `pytest.skip`

## Log 位置 (Log Paths)

```
testlog/
├── CDILog/
│   ├── Before_DiskInfo.txt        ← SMART baseline
│   ├── Before_DiskInfo.json
│   ├── Before_DiskInfo_C.png
│   ├── After_DiskInfo.txt         ← SMART post-test
│   ├── After_DiskInfo.json
│   └── After_DiskInfo_C.png
├── PEPChecker_Log/
│   ├── PBC-Report.html
│   ├── PBC-sleepstudy-report.html
│   ├── PBC-Debug-Log.txt
│   └── PBC-Errors.txt
├── PwrTestLog/
│   ├── pwrtestlog.log
│   └── pwrtestlog.xml
├── sleepstudy-report.html         ← powercfg /sleepstudy 輸出
└── reboot_state.json              ← reboot phase tracking
```

## 設定重點 (Config.json Key Settings)

| 參數 | 預設值 | 說明 |
|---|---|---|
| `pwrtest.cycle_count` | 1 | 睡眠/喚醒次數 |
| `pwrtest.wake_after_seconds` | 60 | 睡眠持續秒數 |
| `sleepstudy.sw_hw_threshold_pct` | 90 | SW/HW DRIPS 最低門檻 (%) |
| `reboot.delay_seconds` | 10 | 重開機前等待秒數 |
| `smart_check.no_increase_attributes` | `["Unsafe Shutdowns"]` | 不能增加的 SMART 屬性 |
| `smart_check.must_be_zero_attributes` | Reallocated/Pending/Uncorrectable | 必須為 0 的錯誤計數 |

## Sleepstudy DRIPS 說明

**SW DRIPS** (Software Residency) 與 **HW DRIPS** (Hardware Residency) 表示裝置在睡眠期間  
進入低功耗狀態的時間比例。數值**愈高愈好**（代表 SSD 正確進入低功耗模式）。

- **通過條件**：SW ≥ 90% 且 HW ≥ 90%  
- **失敗條件**：SW < 90% 或 HW < 90%（SSD 無法正常進入低功耗狀態）

## 疑難排解 (Troubleshooting)

### PEPChecker 執行失敗
- 確認 PHM (步驟 03) 已成功安裝
- 確認 `PEPChecker.exe` 位於 `C:\Program Files\PowerhouseMountain\NDA\collectors\windows\PBC\`
- 以管理員身份執行

### PwrTest 失敗
- 確認系統支援 Modern Standby（`powercfg /a` 顯示 `S0 Low Power Idle`）
- 確認 `pwrtest.exe` 路徑正確（需要 Windows Driver Kit）

### Sleepstudy 無 sleep sessions
- 確認 PwrTest 確實執行了睡眠循環
- 調整 `pwrtest.wake_after_seconds` 拉長睡眠時間（至少 60 秒）

### CDI After 找不到 Before log
- 確認 Phase A 完整執行（步驟 02 成功）
- 確認 `testlog/CDILog/Before_DiskInfo.json` 存在

## 參考資料 (References)

- [STC-2562 計畫文件](../../../../../STC2562_PLAN.md)
- [PEPChecker 設計](../../../../../PEPCHECKER_PLAN.md)
- [STC-1685 (BurnIN) 參考](../stc1685_burnin/test_main.py)
