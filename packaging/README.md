# SSD-TestKit 打包教學

本文件說明如何使用 PyInstaller 將 SSD-TestKit 打包成可執行檔案。

## 環境需求

- Python 3.10+
- PyInstaller 6.18.0+
- 所有測試依賴套件（requirements.txt）

## 配置檔案說明

### build_config.yaml

打包前請先配置 `build_config.yaml`：

```yaml
# 版本號（會自動加到輸出資料夾名稱後面）
version: "1.0.0"

# 可執行檔名稱
project_name: "RunTest"

# 輸出資料夾名稱（會組合成：stc1685_burnin_v1.0.0）
output_folder_name: "stc1685_burnin"

# 要打包的測試專案路徑
test_projects:
  - tests/integration/client_pcie_lenovo_storagedv/stc1685_burnin
```

**參數說明：**
- `version`: 版本號，會自動附加到輸出資料夾名稱
- `project_name`: 生成的 exe 檔案名稱
- `output_folder_name`: 輸出資料夾的基礎名稱（選填，不填則使用測試專案路徑的最後一段）
- `test_projects`: 要打包的測試專案路徑（相對於專案根目錄）

## 打包步驟

### 1. 清理舊檔案（建議）

```powershell
cd C:\automation\ssd-testkit\packaging
Remove-Item dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item *.spec -ErrorAction SilentlyContinue
```

### 2. 執行打包

```powershell
python build.py
```

打包過程會：
1. 自動生成 PyInstaller spec 檔案
2. 編譯成單一 exe 檔案（onefile 模式）
3. 複製相關資源檔案（bin、Config、tests）
4. 建立最終的目錄結構

### 3. 檢查輸出

打包完成後，檔案會在 `dist/` 資料夾：

```
packaging/dist/
  └── stc1685_burnin_v1.0.0/
      ├── RunTest.exe           # 主程式
      ├── bin/                  # 工具程式目錄
      ├── Config/               # 配置檔案目錄
      ├── log/                  # 日誌目錄（執行時自動建立）
      ├── testlog/              # 測試日誌目錄（執行時自動建立）
      ├── tests/                # 測試檔案目錄
      ├── 快速測試.bat          # 便捷腳本（如果有）
      ├── 運行測試.bat
      ├── 運行單個測試.bat
      └── 查看日誌.bat
```

## 使用打包後的程式

### 方法 1: 直接執行（使用預設測試專案）

```powershell
cd dist\stc1685_burnin_v1.0.0
.\RunTest.exe
```

### 方法 2: 使用便捷批次檔

雙擊執行：
- `快速測試.bat` - 執行單一測試快速驗證
- `運行測試.bat` - 執行完整測試套件
- `運行單個測試.bat` - 互動式選擇測試
- `查看日誌.bat` - 查看日誌檔案

### 方法 3: 指定測試專案

```powershell
.\RunTest.exe --test tests\integration\client_pcie_lenovo_storagedv\stc1685_burnin
```

### 方法 4: 傳遞 pytest 參數

```powershell
.\RunTest.exe --pytest-args -k test_01_precondition -v
```

