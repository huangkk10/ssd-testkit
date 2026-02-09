# STC-1685 建立完成總結

## 已建立的檔案和目錄

### 📁 目錄結構

```
tests/integration/stc1685/
├── Config/
│   └── Config.json              ✅ 測試配置文件
├── bin/
│   ├── .gitignore              ✅ Git 忽略規則
│   ├── README.md               ✅ 二進制文件說明
│   ├── BurnIn/                 ✅ BurnIN 工具目錄 (需手動放置文件)
│   ├── H2test/                 ✅ H2test 工具目錄 (需手動放置文件)
│   └── SmiCli/                 ✅ SmiCli 工具目錄 (需手動放置文件)
├── test_burnin_h2test.py        ✅ 主測試文件
└── README.md                    ✅ 測試說明文件
```

### 📄 規劃文件

- `docs/STC-1685_Migration_Plan.md` ✅ 完整的遷移計畫文件

## 已實現的測試步驟

### ✅ Step 1: test_01_precondition
**前置條件設定**
- 清理 MEI 資料夾
- 建立 log 目錄
- 配置系統設定 (電源、UAC、休眠、磁碟重組)
- 檢查 DUT 資訊
- 清除並格式化測試磁碟

### ✅ Step 2: test_02_install_burnin  ⭐ (您要求的第一個流程)
**安裝 BurnIN 測試工具**
- 檢查 BurnIN 是否已安裝
- 執行靜默安裝
- 複製授權文件
- 驗證安裝成功

### ✅ Step 3: test_03_setup_h2test
**設定 H2test 配置**
- 配置 H2test 參數
- 計算測試大小
- 刪除舊測試資料

### ✅ Step 4: test_04_smicli
**執行 SmiCli**
- 收集初始 SMART 資訊

### 🔄 Step 5-7: 待實現
- test_05_h2test_write - 執行 H2test 寫入測試
- test_06_burnin_with_smartcheck - BurnIN + SmartCheck 並行測試
- test_07_verify_results - 驗證結果

## 技術特點

### 使用新框架
- ✅ **pytest** 測試框架
- ✅ **BaseTestCase** 基礎類別
- ✅ **@step** 裝飾器標記測試步驟
- ✅ **threading** 替代 asyncio (準備用於並行測試)

### 參考實現
- 參考 `tests/integration/stc1742/test_modern_standby.py` 的框架結構
- 參考 `testcase/.../STC-625/.../main.py` 的測試邏輯
- 使用 `lib/testtool/BurnIN.py` 的 install() 方法

## 下一步操作

### 1️⃣ 準備測試工具 (必須)
將以下文件放置到對應目錄：

**BurnIn 工具** (放在 `bin/BurnIn/`):
- `bitwindows.exe` - BurnIN 安裝程式
- `key.dat` - 授權文件

**H2test 工具** (放在 `bin/H2test/`):
- `h2testw.exe` - H2test 執行檔

**SmiCli 工具** (放在 `bin/SmiCli/`):
- `smicli.exe` - SmiCli 工具

### 2️⃣ 建立 BurnIN 配置文件 (可選)
如需自訂 BurnIN 測試配置，建立:
- `Config/BIT_Config/BurnInScript.bits`
- `Config/BIT_Config/BurnInScript.bitcfg`

### 3️⃣ 建立 SmiCli 配置 (可選)
如需使用 SmiCli，建立:
- `Config/SmiCli.json`

### 4️⃣ 執行測試

#### 測試前兩個步驟 (前置條件 + BurnIN 安裝):
```powershell
cd c:\automation\tests\integration\stc1685
pytest test_burnin_h2test.py -k "test_01 or test_02" -v -s
```

#### 只測試 BurnIN 安裝:
```powershell
pytest test_burnin_h2test.py::TestSTC1685BurnInH2test::test_02_install_burnin -v -s
```

#### 執行所有已實現的測試:
```powershell
pytest test_burnin_h2test.py -v -s
```

## 重要提醒

### ⚠️ 磁碟格式化警告
test_01_precondition 會格式化測試磁碟，請確保:
1. 在 `Config/Config.json` 中設定正確的 `test_drive_letter`
2. 確認該磁碟可以被格式化 (不是系統磁碟)
3. 備份重要資料

### ⚠️ 管理員權限
測試需要管理員權限來:
- 安裝 BurnIN
- 格式化磁碟
- 修改系統設定 (UAC, 電源計劃等)

### ⚠️ BurnIN 授權
需要有效的 `key.dat` 授權文件才能使用 BurnIN Test。

## 配置說明

### 主要配置項 (Config/Config.json)

```json
{
  "burnin": {
    "install_path": "C:\\Program Files\\BurnInTest",  // BurnIN 安裝路徑
    ...
  },
  "h2test": {
    "fill_disk_percentage": 50,  // 寫入磁碟的百分比
    ...
  },
  "disk_utility": {
    "test_drive_letter": "K",    // ⚠️ 測試磁碟代號
    "format_type": "NTFS",        // 格式化類型
    ...
  },
  "smartcheck": {
    "enable": true,               // 是否啟用 SMART 監控
    ...
  }
}
```

## 文檔參考

1. **詳細遷移計畫**: [docs/STC-1685_Migration_Plan.md](../../../docs/STC-1685_Migration_Plan.md)
2. **測試說明**: [README.md](README.md)
3. **參考框架**: [tests/integration/stc1742/test_modern_standby.py](../stc1742/test_modern_standby.py)
4. **原始測試**: [testcase/.../STC-625/.../main.py](../../../testcase/Client_PCIe_Standard/STC-625_H2test_write_half_BurnIn_Test/latest/main.py)

## 總結

✅ **已完成**:
- 建立完整的目錄結構
- 實現前 4 個測試步驟 (包括您要求的 BurnIN 安裝)
- 建立詳細的規劃文件
- 提供完整的配置和說明文件

🔄 **待完成** (可根據需要擴展):
- Step 5: H2test 寫入測試
- Step 6: BurnIN + SmartCheck 並行測試 (使用 threading)
- Step 7: 結果驗證和報告生成

📝 **建議**:
1. 先測試前兩個步驟，確保基礎功能正常
2. 再逐步實現後續的測試步驟
3. 參考規劃文件了解完整的實現細節
