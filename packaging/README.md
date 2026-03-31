# SSD-TestKit 打包說明

本文件說明如何使用 PyInstaller 將 SSD-TestKit 打包成可執行檔，以及如何使用打包後的程式。

---

## 目錄

1. [環境需求](#1-環境需求)
2. [目錄結構](#2-目錄結構)
3. [設定 build_config.yaml](#3-設定-build_configyaml)
4. [執行打包](#4-執行打包)
5. [build.py 參數說明](#5-buildpy-參數說明)
6. [輸出目錄結構](#6-輸出目錄結構)
7. [使用打包後的程式](#7-使用打包後的程式)
8. [RunTest.exe 參數說明](#8-runtestexe-參數說明)
9. [打包機制說明](#9-打包機制說明)
10. [常見問題](#10-常見問題)

---

## 1. 環境需求

| 項目 | 版本需求 |
|------|---------|
| Python | 3.10+ |
| PyInstaller | 6.18.0+ |
| PyYAML | 任意 |
| 其他相依套件 | 詳見 `requirements.txt` |

安裝依賴：

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

---

## 2. 目錄結構

```
packaging/
├── build.bat               # 一鍵打包腳本（Windows）
├── build.py                # 打包主程式
├── build_config.yaml       # 打包設定檔
├── build_output.log        # 每次打包自動產生的完整 log（UTF-8）
├── path_manager.py         # 凍結/開發環境路徑解析
├── run_test.py             # EXE 入口程式
├── run_test.spec           # PyInstaller spec 檔（已納入 git）
├── run_test_hook.py        # PyInstaller runtime hook
├── README.md               # 本文件
├── build/                  # PyInstaller 中間產物（gitignore）
├── dist/                   # 打包輸出目錄（gitignore）
│   └── SSD_TestKit_20260330/
│       ├── RunTest.exe
│       ├── pytest.ini
│       ├── bin/
│       └── tests/
└── release/                # ZIP 壓縮包輸出（gitignore）
    └── SSD_TestKit_20260330.zip
```

---

## 3. 設定 build_config.yaml

```yaml
# 版本號
version: "1.0.0"

# 可執行檔名稱（生成 RunTest.exe）
project_name: "RunTest"

# Release 命名（dist 子資料夾名稱 與 ZIP 檔名）
# 支援 {date} 佔位符，替換為執行當日日期（YYYYMMDD）
# 留空則使用預設命名：{test_root 最後一段}_v{version}
release_name: "SSD_TestKit_{date}"

# 自動打包此目錄下所有含 test_main.py 的子資料夾
# 新增 testcase 資料夾後不需要修改此檔，會自動被發現
test_root: tests/integration/test_case

# RunTest.exe 不帶 --test 參數執行時的預設 testcase
default_test: tests/integration/test_case/stc2557_adk_s3s4s5
```

> 若需要只打包特定 testcase（舊行為），可改用 `test_projects` 明確列出：
> ```yaml
> test_projects:
>   - tests/integration/test_case/stc1685_burnin
> ```

---

## 4. 執行打包

### 方式 A：一鍵批次檔（推薦）

```bat
cd packaging
build.bat
```

| 用法 | 說明 |
|------|------|
| `build.bat` | 一般打包（重用現有 spec） |
| `build.bat --check` | 只跑打包前確認，不執行打包 |
| `build.bat --clean` | 先清除 `dist/` 和 `build/` 再打包 |
| `build.bat --no-release` | 跳過 ZIP 壓縮包的建立 |
| `build.bat --spec-only` | 只產生 spec 檔，不編譯 EXE |
| `build.bat --new-spec` | 強制重新從範本產生 spec 檔後再打包 |

> 打包結束後，完整輸出會同時顯示在螢幕上，並自動寫入 `packaging/build_output.log`。

### 方式 B：直接執行 Python

```powershell
cd C:\automation\ssd-testkit\packaging
python build.py
python build.py --clean
python build.py --no-release
```

---

## 5. build.py 參數說明

```
usage: build.py [--check] [--clean] [--no-release] [--spec-only] [--new-spec]
                [--show-config] [--config CONFIG]

選項：
  --check         打包前確認（pre-flight check）：驗證路徑、顯示打包內容預覽後退出，不執行打包
  --clean         打包前先刪除 dist/ 和 build/ 目錄
  --no-release    跳過建立 ZIP 壓縮包
  --spec-only     只產生 run_test.spec，不執行 PyInstaller
  --new-spec      刪除現有 spec 並重新從範本產生
  --show-config   顯示目前設定內容後退出
  --config FILE   指定設定檔路徑（預設：build_config.yaml）
```

---

## 6. 輸出目錄結構

每次打包，`post-processing` 會先 **完整刪除** 舊的輸出資料夾，再重建，確保不殘留舊版檔案：

```
packaging/dist/
└── SSD_TestKit_20260330/              ← 每次 build 都會先刪除再重建
    ├── RunTest.exe                    # 主程式（onefile 模式，無需 Python）
    ├── pytest.ini                     # pytest 設定（rootdir 錨點）
    ├── bin/                           # 工具（來自專案根目錄 ssd-testkit/bin/）
    │   ├── chocolatey/
    │   └── installers/
    │       ├── BurnIn/
    │       ├── CrystalDiskInfo/
    │       ├── PHM/
    │       ├── SmiCli/
    │       ├── SmiWinTools/
    │       └── WindowsADK/
    └── tests/
        └── integration/
            └── test_case/             ← test_root 下所有 testcase 自動打包
                ├── stc1685_burnin/
                │   ├── test_main.py
                │   ├── conftest.py
                │   └── Config/
                ├── stc2557_adk_s3s4s5/    ← default_test（無 --test 時的預設）
                │   ├── test_main.py
                │   ├── conftest.py
                │   └── Config/
                ├── stc2562_modern_standby/
                │   ├── test_main.py
                │   ├── conftest.py
                │   └── Config/
                └── stc547_intel_rvp_modern_standby/
                    ├── test_main.py
                    ├── conftest.py
                    └── Config/

packaging/release/
└── SSD_TestKit_20260330.zip           # 可交付的壓縮包
```

> **新增 testcase 不需要改任何設定**：只要在 `tests/integration/test_case/` 下建立含 `test_main.py` 的資料夾，下次打包時會自動包入。

---

## 7. 使用打包後的程式

```powershell
cd dist\SSD_TestKit_20260330

# 執行預設 testcase（build_config.yaml 的 default_test）
.\RunTest.exe

# 執行指定 testcase
.\RunTest.exe --test tests\integration\test_case\stc1685_burnin\test_main.py
.\RunTest.exe --test tests\integration\test_case\stc2557_adk_s3s4s5\test_main.py

# 試跑（只顯示 pytest 指令，不實際執行）
.\RunTest.exe --dry-run
.\RunTest.exe --test tests\integration\test_case\stc1685_burnin\test_main.py --dry-run

# 顯示說明
.\RunTest.exe --help

# 顯示路徑資訊（偵錯用）
.\RunTest.exe --show-paths
```

---

## 8. RunTest.exe 參數說明

```
usage: RunTest.exe [--test PATH] [--markers EXPR] [--verbose]
                   [--log-level LEVEL] [--output DIR] [--report FORMAT]
                   [--dry-run] [--show-paths] [--pytest-args ...]

測試目標：
  --test, -t PATH       指定測試檔案、目錄或測試類別

pytest 篩選：
  --markers, -m EXPR    pytest marker 表達式
                        例：-m "slow" 或 -m "client_lenovo and feature_burnin"

輸出控制：
  --verbose, -v         增加詳細程度（可重複：-v -vv -vvv）
  --log-level, -l       日誌等級：DEBUG / INFO / WARNING / ERROR / CRITICAL
                        （預設：INFO）
  --output, -o DIR      測試結果輸出目錄（預設：./testlog）
  --report FORMAT       報告格式：none / term / html（預設：term）

工具選項：
  --dry-run             顯示 pytest 指令但不執行
  --show-paths          顯示路徑資訊後退出
  --pytest-args ...     直接傳遞給 pytest 的額外參數

範例：
  RunTest.exe
  RunTest.exe -v
  RunTest.exe --markers "smoke"
  RunTest.exe --dry-run
  RunTest.exe --pytest-args -k test_01_precondition -v
  RunTest.exe --show-paths
```

---

## 9. 打包機制說明

### onefile 模式

PyInstaller 使用 `onefile` 模式，執行時解壓縮到 `%TEMP%\\_MEIxxxxxx\`（`sys._MEIPASS`），包含：
- `base_library.zip`：Python 標準函式庫
- `win32\`：pywin32 C extension DLLs（`win32gui.pyd` 等）
- 所有 `hiddenimports` 模組

### sys.path 保護

`run_test_hook.py` 與 `path_manager.py` 在啟動時清理 `sys.path`，確保：
- `_MEIPASS` 及其所有子路徑（`base_library.zip`、`win32\`）被保留
- 主機環境的 `C:\automation\framework` 等不汙染打包模組

### rootdir 鎖定

`pytest.ini` 同時存在於 `_MEIPASS`（PyInstaller 打包）和 `dist/stc1685_burnin_v1.0.0/`（build 後複製）。  
`run_test.py` 強制加入 `--rootdir <app_dir>` 參數，防止 pytest 向上掃描找到主機上的 `conftest.py`。

### WinIoEx.sys 驅動鎖定處理

若 `bin/SmiCli/WinIoEx.sys` 在上一次測試後被 Windows Kernel 鎖定，`build.py` 會：
1. 在 Registry `HKLM\SYSTEM\CurrentControlSet\Services` 搜尋對應服務
2. 執行 `sc stop <service>` + `sc delete <service>`
3. 等待 1 秒後重試複製

---

## 10. 常見問題

### Q: 執行 `RunTest.exe` 出現 `ModuleNotFoundError`

確認打包時的 `hiddenimports` 涵蓋所需模組。重新打包並加入 `--new-spec`：

```bat
build.bat --new-spec --clean
```

### Q: build 時出現 `[Errno 13] Permission denied: WinIoEx.sys`

正常情況下 `build.py` 會自動處理（停止並刪除 kernel driver 服務後重試）。  
若仍失敗，請重開機後再執行 `build.bat --clean`。

### Q: 想確認打包了哪些模組

查看 PyInstaller 分析報告：

```
packaging/build/run_test/warn-run_test.txt   # 警告（找不到的模組）
packaging/build/run_test/xref-run_test.html  # 完整相依關係圖
```

### Q: 打包後的程式找不到 `Config.json`

確認 `build_config.yaml` 裡的 `test_projects` 路徑正確，且對應資料夾下有 `Config/` 目錄。

### Q: 想查看詳細打包 log

每次 `build.bat` 執行後，完整 log 存於：

```
packaging/build_output.log
```

---
