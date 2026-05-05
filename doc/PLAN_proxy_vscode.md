# VS Code Proxy 自動切換設定

## 快速操作

### 首次安裝（僅需一次，需系統管理員）

```powershell
Set-ExecutionPolicy Bypass -Scope Process; & C:\proxy\setup_proxy.ps1 -Enable
```

完成後開機會自動生效，**不需要再執行**。

---

### 切換網路後（回辦公室 / 離開辦公室）

```powershell
Set-ExecutionPolicy Bypass -Scope Process; & tools\refresh_proxy.ps1
```

接著**重啟 VS Code**。腳本會自動重新探測 proxy 狀態並更新 VS Code settings，輸出範例：

```
=== 目前狀態 ===
  PAC 回傳   : function FindProxyForURL(url,host){return "PROXY 10.10.10.190:3128; DIRECT";}
  VS Code proxy: http://10.10.10.190:3128

請重啟 VS Code 讓設定生效。
```

或（proxy 不通時）：

```
=== 目前狀態 ===
  PAC 回傳   : function FindProxyForURL(url,host){return "DIRECT";}
  VS Code proxy: (未設定，走 DIRECT)

請重啟 VS Code 讓設定生效。
```

---

### 診斷

```powershell
Set-ExecutionPolicy Bypass -Scope Process; & C:\proxy\diagnose.ps1
```

---

## 目標

- Proxy 有通時：VS Code 透過 `10.10.10.190:3128` 連外網
- Proxy 沒通時：VS Code 自動走 DIRECT，不卡住

---

## 核心問題（已釐清）

原本的想法是讓 VS Code 繼承 Windows 系統 PAC 設定（`AutoConfigURL`），但這個方法**不夠**：

| 元件 | PAC `PROXY x; DIRECT` 行為 |
|---|---|
| Chrome / Edge | ✅ proxy 失敗自動 fallback DIRECT |
| VS Code（Node.js Extension Host） | ❌ 不實作 fallback，proxy TCP timeout 後直接失敗、卡住 |

**正確解法**：讓一個背景程式持續探測 proxy，並直接寫入 VS Code `settings.json` 的 `http.proxy`，讓 VS Code 在 proxy 通/不通之間自動切換。

---

## 實際可行的解法：動態 PAC Server + 直寫 VS Code settings

### 架構

```
pac_server.ps1（Scheduled Task，開機自動執行）
  │
  ├─ 每 15 秒  TCP 探測 10.10.10.190:3128（timeout 2s）
  │
  ├─ proxy 可達  → VS Code settings.json: "http.proxy" = "http://10.10.10.190:3128"
  │               PAC 回傳: "PROXY 10.10.10.190:3128; DIRECT"
  │
  └─ proxy 不可達 → VS Code settings.json: 移除 "http.proxy"
                    PAC 回傳: "DIRECT"
```

**關鍵設計決策**：

- VS Code 的 Node.js Extension Host（Copilot 在這裡執行）**不像 Chrome 那樣實作 `PROXY x; DIRECT` fallback**。PAC 返回 `PROXY x; DIRECT` 時，VS Code 嘗試 proxy TCP → timeout 30s+ → Copilot 卡死。  
  解法是讓 PAC server 在 proxy 不通時直接回 `DIRECT`，同時主動寫入 `settings.json` 的 `http.proxy`，繞過 VS Code 的 PAC fallback 問題。
- Windows 系統 `AutoConfigURL` 用 `file://` 路徑在 Electron/VS Code 會被靜默忽略，**必須改用 `http://127.0.0.1:18888/proxy.pac`**。
- PAC server 用 Windows Scheduled Task 管理，比 `Start-Job` 更可靠（重開機後自動重啟、session 結束不消失）。

---

### 檔案清單

| 路徑 | 說明 |
|---|---|
| `C:\proxy\pac_server.ps1` | 核心服務：探測 proxy、動態 PAC、同步 VS Code settings |
| `C:\proxy\setup_proxy.ps1` | 一鍵安裝/移除 Scheduled Task 與 Windows registry |
| `C:\proxy\diagnose.ps1` | 診斷工具：檢查所有元件狀態 |

---

### 安裝步驟（一次性，需要系統管理員）

```powershell
# 以系統管理員執行
Set-ExecutionPolicy Bypass -Scope Process
& C:\proxy\setup_proxy.ps1 -Enable
```

輸出應為：

```
Adding URL ACL for http://127.0.0.1:18888/ ...
[OK] Scheduled Task 'ProxyPacServer' registered (auto-start at logon)
[OK] PAC server verified: http://127.0.0.1:18888/proxy.pac is responding
[OK] Registry: AutoConfigURL=http://127.0.0.1:18888/proxy.pac, ProxyEnable=0 (PAC mode)
```

移除：

```powershell
& C:\proxy\setup_proxy.ps1 -Disable
```

---

### pac_server.ps1（完整內容）

```powershell
# PAC HTTP Server + VS Code proxy sync
# - Probes 10.10.10.190:3128 every 15s
# - Serves dynamic PAC on http://127.0.0.1:18888/proxy.pac
# - Updates VS Code settings.json http.proxy automatically

param(
    [string]$ProxyHost      = "10.10.10.190",
    [int]   $ProxyPort      = 3128,
    [int]   $ListenPort     = 18888,
    [int]   $ProbeTTLSec    = 15,
    [int]   $ProbeTimeoutMs = 2000
)

$VsCodeSettingsPaths = @(
    "$env:APPDATA\Code - Insiders\User\settings.json",
    "$env:APPDATA\Code\User\settings.json"
)

function Test-TcpReachable {
    param([string]$H, [int]$P, [int]$Ms)
    try {
        $tcp  = [System.Net.Sockets.TcpClient]::new()
        $task = $tcp.ConnectAsync($H, $P)
        $ok   = $task.Wait($Ms) -and $tcp.Connected
        try { $tcp.Close() } catch {}
        return $ok
    } catch { return $false }
}

function Update-VsCodeProxy {
    param([string]$ProxyUrl)   # empty string = DIRECT
    foreach ($path in $VsCodeSettingsPaths) {
        if (-not (Test-Path $path)) { continue }
        try {
            $raw = Get-Content $path -Raw -Encoding UTF8
            # Strip single-line // comments (JSONC) before parsing
            $json = $raw -replace '(?m)^\s*//.*$', ''
            $obj  = $json | ConvertFrom-Json
            if ($ProxyUrl -ne "") {
                $obj | Add-Member -Force -NotePropertyName "http.proxy" -NotePropertyValue $ProxyUrl
            } elseif ($obj.PSObject.Properties.Name -contains "http.proxy") {
                $obj.PSObject.Properties.Remove("http.proxy")
            }
            $obj | Add-Member -Force -NotePropertyName "http.proxySupport" -NotePropertyValue "override"
            $obj | ConvertTo-Json -Depth 20 | Set-Content $path -Encoding UTF8
        } catch {
            Write-Warning "Could not update $path : $_"
        }
    }
}

$probeTime = [datetime]::MinValue
$proxyUp   = $false
$lastState = $null

# Initial sync on startup
$proxyUp   = Test-TcpReachable -H $ProxyHost -P $ProxyPort -Ms $ProbeTimeoutMs
$probeTime = [datetime]::Now
$lastState = $proxyUp
$proxyUrl  = if ($proxyUp) { "http://${ProxyHost}:${ProxyPort}" } else { "" }
Update-VsCodeProxy -ProxyUrl $proxyUrl

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add("http://127.0.0.1:${ListenPort}/")
try {
    $listener.Start()
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()

        if (([datetime]::Now - $probeTime).TotalSeconds -gt $ProbeTTLSec) {
            $proxyUp   = Test-TcpReachable -H $ProxyHost -P $ProxyPort -Ms $ProbeTimeoutMs
            $probeTime = [datetime]::Now
            if ($proxyUp -ne $lastState) {
                $lastState = $proxyUp
                $proxyUrl  = if ($proxyUp) { "http://${ProxyHost}:${ProxyPort}" } else { "" }
                Update-VsCodeProxy -ProxyUrl $proxyUrl
            }
        }

        $pac = if ($proxyUp) {
            "function FindProxyForURL(url,host){return `"PROXY ${ProxyHost}:${ProxyPort}; DIRECT`";}"
        } else {
            "function FindProxyForURL(url,host){return `"DIRECT`";}"
        }

        $buf = [System.Text.Encoding]::UTF8.GetBytes($pac)
        $ctx.Response.ContentType     = "application/x-ns-proxy-autoconfig"
        $ctx.Response.ContentLength64 = $buf.Length
        $ctx.Response.Headers.Add("Cache-Control", "no-cache, no-store, max-age=0")
        $ctx.Response.OutputStream.Write($buf, 0, $buf.Length)
        $ctx.Response.Close()
    }
} finally {
    $listener.Stop()
}
```

---

### VS Code settings.json 狀態

`pac_server.ps1` 啟動時會自動寫入，無需手動設定：

| Proxy 狀態 | `http.proxy` | `http.proxySupport` |
|---|---|---|
| Proxy 可達 | `http://10.10.10.190:3128` | `override` |
| Proxy 不可達 | （移除此設定） | `override` |

> `"override"` 表示 VS Code 使用 `http.proxy` 的值（若未設定則直連），不繼承系統 proxy。這樣可以避免 VS Code 自行讀取 Windows AutoConfigURL 後嘗試 PAC fallback 的 timeout 問題。

---

### 診斷指令

```powershell
# 完整診斷
Set-ExecutionPolicy Bypass -Scope Process; & C:\proxy\diagnose.ps1

# 快速檢查
Get-ScheduledTask -TaskName "ProxyPacServer" | Select-Object State
Invoke-WebRequest http://127.0.0.1:18888/proxy.pac -UseBasicParsing | Select-Object @{n="PAC";e={[Text.Encoding]::UTF8.GetString($_.Content)}}
```

---

### 切換網路後的處理

proxy 狀態改變時（例如進辦公室接了內網、或離開辦公室），`pac_server.ps1` 最多 15 秒後會自動更新 `settings.json`，但 **VS Code 需要重啟**才能讀取新設定。

---

### 注意事項

**git 需要獨立設定**（不讀系統 proxy）：

```powershell
git config --global http.proxy http://10.10.10.190:3128   # proxy 通時
git config --global --unset http.proxy                     # proxy 不通時
```

**pip / npm 等工具**用環境變數：

```powershell
$env:HTTP_PROXY  = "http://10.10.10.190:3128"
$env:HTTPS_PROXY = "http://10.10.10.190:3128"
```

