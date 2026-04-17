# Skill 與流程文件更新計畫

## 1. 目標

建立一份可執行的更新計畫，修正目前「工具打包/上傳/準備」相關 skill 與文件和實際腳本行為不一致的問題，確保後續 agent 回答與實作一致。

## 2. 現況摘要（已確認）

- 主要流程腳本：
  - `tool-manager/upload_tools_to_nexus.ps1`：負責 nupkg 上傳 Nexus + installer zip 備份到 NAS。
  - `tool-manager/prepare_testcase.ps1`：負責下載 nupkg + 從 NAS 解壓 installer 到本地。
- 版本與路徑來源：`lib/testtool/tools-registry.yaml`。
- 安裝行為入口：
  - `bin/chocolatey/scripts/install_packages.ps1`
  - `lib/testtool/choco_manager.py`
- 關鍵事實：`prepare_testcase.ps1` 目前不執行 `choco install`，只做「準備檔案」。

## 3. 需修改範圍

### A. 高優先：tool-manager skill

目標檔案：`.claude/skills/tool-manager/SKILL.md`

需調整內容：
1. 明確標示 `prepare_testcase` 的責任邊界是「下載/解壓」，不是安裝。
2. 更新 `windows-adk` 範例與說明，對齊 `tools-registry.yaml` 目前有 `source_dir`/`nexus_path` 的實作。
3. 補充安裝入口導引：若要實際安裝，應使用 `install_packages.ps1` 或 `ChocoManager`。
4. 保留既有 Nexus/NAS 連線注意事項（curl 參數與 net use），避免回歸。

### B. 中優先：chocolatey-packaging skill

目標檔案：`.claude/skills/chocolatey-packaging/SKILL.md`

需調整內容：
1. 對齊本 repo 的 pack 實務：nupkg 常由 `packages/<id>/<version>/` 底下 nuspec 產生。
2. 補上與 `tools-registry.yaml` 的關係（版本與 source_dir/nexus_path 作為 tool-manager 流程來源）。
3. 補充和 `upload_tools_to_nexus.ps1`、`prepare_testcase.ps1` 的銜接段落，避免只談單點打包。
4. 將「打包」「上傳」「準備」「安裝」四階段界線寫清楚。

### C. 中優先：tool-manager 使用文件

目標檔案：`tool-manager/TOOLS-GUIDE.md`

需調整內容：
1. 修正過時 Nexus 範例（`nexus.internal/choco-hosted`）為實際預設（`10.252.170.171/choco-hosted-nas`）。
2. 刪除或修正 `prepare_testcase.ps1 -Force`（目前腳本未提供此參數）。
3. 修正「prepare 會安裝工具」描述，改為「prepare 只準備快取與 installer 檔案」。

## 4. 執行步驟

1. 先更新 `.claude/skills/tool-manager/SKILL.md`（高優先）。
2. 再更新 `.claude/skills/chocolatey-packaging/SKILL.md`（中優先）。
3. 同步更新 `tool-manager/TOOLS-GUIDE.md`（中優先，避免使用者文件誤導）。
4. 最後做一次一致性檢查（字詞與流程對齊）。

## 5. 驗收標準（Definition of Done）

1. 任一文件不再描述 `prepare_testcase` 會直接安裝工具。
2. 所有 Nexus repo 名稱與 URL 不再使用過時值（除非明確標示為示例）。
3. skills 內容可正確回答以下問題：
   - 如何新增工具並上傳？
   - 如何讓新機器準備好必要工具檔案？
   - 何時使用 `prepare_testcase`，何時使用 `install_packages`/`ChocoManager`？
4. 至少一份文件清楚描述 `tools-registry.yaml` 是版本/路徑來源。

## 6. 風險與對策

- 風險：只改 skill 未改 TOOLS-GUIDE，造成內外文件不一致。
  - 對策：skill 與 TOOLS-GUIDE 同一批次更新。
- 風險：未標註腳本責任邊界，agent 仍可能誤導安裝流程。
  - 對策：在兩份 skill 都加入「Prepare != Install」明確段落。

## 7. 建議時程

- Day 1：完成 A + B 初稿修正。
- Day 1：完成 C 並做一致性檢查。
- Day 2：依 reviewer 意見微調。

## 8. 後續可選強化（非本次必要）

1. 在 `prepare_testcase.ps1` 加入 `-Install` 可選參數（若未來要支援一鍵安裝）。
2. 在 CI 增加文件一致性檢查（關鍵字規則：Prepare/Install/Repo URL）。
3. 將 Nexus/NAS 連線資訊集中到單一設定檔，減少多處維護。