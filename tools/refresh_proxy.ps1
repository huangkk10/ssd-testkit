# 強制重新探測 proxy 狀態，並更新 VS Code settings.json
# 不需要系統管理員，但 Scheduled Task 必須先用 setup_proxy.ps1 -Enable 安裝過

$taskName = "ProxyPacServer"
$pacUrl   = "http://127.0.0.1:18888/proxy.pac"

# 1. 確保 Scheduled Task 在跑
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Warning "Scheduled Task '$taskName' 不存在。請先以系統管理員執行："
    Write-Warning "  Set-ExecutionPolicy Bypass -Scope Process; & C:\proxy\setup_proxy.ps1 -Enable"
    exit 1
}

if ($task.State -ne "Running") {
    Write-Host "啟動 $taskName ..."
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 3
}

# 2. 先停再啟以強制重新執行 startup 探測邏輯（最可靠的方式）
Write-Host "重新探測 proxy 狀態..."
Stop-ScheduledTask  -TaskName $taskName -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Start-ScheduledTask -TaskName $taskName

# 3. 等待 server 就緒（最多 5s）
$ready = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri $pacUrl -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}

if (-not $ready) {
    Write-Warning "PAC server 未回應，請檢查 Scheduled Task 狀態。"
    exit 1
}

# 4. 顯示結果
$pac     = [System.Text.Encoding]::UTF8.GetString((Invoke-WebRequest $pacUrl -UseBasicParsing).Content)
$vscPath = "$env:APPDATA\Code - Insiders\User\settings.json"
$proxy   = if (Test-Path $vscPath) {
    ((Get-Content $vscPath -Raw) -replace '(?m)^\s*//.*$','') | ConvertFrom-Json | Select-Object -ExpandProperty "http.proxy" -ErrorAction SilentlyContinue
} else { "(settings.json not found)" }

Write-Host ""
Write-Host "=== 目前狀態 ==="
Write-Host "  PAC 回傳   : $pac"
Write-Host "  VS Code proxy: $(if ($proxy) { $proxy } else { '(未設定，走 DIRECT)' })"
Write-Host ""
Write-Host "請重啟 VS Code 讓設定生效。"
