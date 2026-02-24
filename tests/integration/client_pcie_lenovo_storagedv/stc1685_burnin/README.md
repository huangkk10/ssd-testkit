# STC-1685: BurnIN Installation Test

## 概述 (Overview)

簡單的 BurnIN 安裝測試。

## 測試流程 (Test Flow)

1. **前置條件** (Precondition)
   - 建立 log 目錄

2. **安裝 BurnIN** (Install BurnIN)
   - 安裝 BurnIN Test 工具

## 目錄結構 (Directory Structure)

```
stc1685/
├── Config/
│   └── Config.json           # 主配置文件
├── bin/                      # 測試工具 (需手動放置)
│   └── BurnIn/
│       ├── bitwindows.exe   # BurnIN 安裝程式
│       └── key.dat          # 授權文件
├── test_burnin.py            # 主測試文件
└── README.md                 # 本文件
```

## 執行測試 (Run Test)

### 完整測試

```powershell
cd c:\automation\tests\integration\stc1685
pytest test_burnin.py -v -s
```

### 執行特定步驟

```powershell
# 只執行 BurnIN 安裝
pytest test_burnin.py::TestSTC1685BurnIN::test_02_install_burnin -v -s
```

## 注意事項 (Notes)

1. **BurnIN 授權**: 需要有效的 `key.dat` 授權文件
2. **管理員權限**: 建議以管理員身份執行

## 疑難排解 (Troubleshooting)

### BurnIN 安裝失敗
- 檢查 `bitwindows.exe` 是否存在於 `bin/BurnIn/` 目錄
- 檢查是否有管理員權限
- 查看 log 中的錯誤訊息

## 參考資料 (References)

- [測試遷移計畫](../../../docs/STC-1685_Migration_Plan.md)
- [STC-1742 參考框架](../stc1742/test_modern_standby.py)


# STC-1685 Burnin Test — 執行說明

**Package：** `STC-1685_Burnin_test_20260224`
**Build Date：** 2026-02-24

---

## 前置需求

| 項目 | 說明 |
|------|------|
| 執行權限 | **以系統管理員身份執行** (Administrator) |
| BurnIN 授權 | `bin\BurnIn\key.dat` 需存在且有效 |
| BurnIN 安裝檔 | `bin\BurnIn\bitwindows.exe` 需存在 |
| 測試磁碟 | DiskID 0，需可建立 D 槽 (NTFS / 10 GB) |

---

## 目錄結構

```
STC-1685_Burnin_test_20260224\
├── RunTest.exe                          ← 執行入口
├── Config\
│   └── Config.json                      ← 主設定檔
├── bin\
│   ├── BurnIn\
│   │   ├── bitwindows.exe
│   │   ├── key.dat
│   │   └── Configs\
│   │       ├── BurnInScript.bits
│   │       └── BurnInScript.bitcfg
│   └── SmiWinTools\
│       └── SmartCheck.bat
└── tests\
    └── integration\
        └── client_pcie_lenovo_storagedv\
            └── stc1685_burnin\
                └── test_main.py
```

---

## 執行指令

**完整測試（建議）**

```powershell
cd STC-1685_Burnin_test_20260224
.\RunTest.exe --test tests\integration\client_pcie_lenovo_storagedv\stc1685_burnin\test_main.py -v
```

**指定 markers 執行**

```powershell
.\RunTest.exe
```


---

## 測試流程

1. **Precondition** — 建立 log 目錄
2. **H2test Write Half** — 寫入磁碟 50% 容量進行資料完整性測試
3. **BurnIN 安裝** — 自動安裝 BurnInTest 工具
4. **BurnIN 執行** — 執行 BurnIN 壓力測試（預設 1440 分鐘 / 24 小時）
5. **SMART Monitor** — 全程監控 SSD SMART 數據

---

## 設定重點（Config.json）

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `burnin.timeout_minutes` | 1500 | 整體 timeout |
| `burnin.test_duration_minutes` | 1440 | BurnIN 測試時長（24 小時） |
| `burnin.test_drive_letter` | D | 測試磁碟代號 |
| `h2test.fill_disk_percentage` | 50 | 寫入比例 50% |
| `smartcheck.total_time` | 10080 | SMART 監控時間（分鐘） |

---

## Log 位置

```
./log/STC-1685/          ← 測試 log
./testlog/Burnin.log     ← BurnIN log
./testlog/H2test/        ← H2test log
./testlog/SmartLog/      ← SMART log
./testlog/Burnin.png     ← BurnIN 截圖（錯誤時自動截圖）
```

---

