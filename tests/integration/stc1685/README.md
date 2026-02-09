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
