<#
.SYNOPSIS
    Detect proxy availability and apply/clear git http.proxy accordingly.

.DESCRIPTION
    Tests TCP connectivity to the configured proxy server.
    - If reachable  → sets git global http.proxy and https.proxy
    - If unreachable → clears git global http.proxy and https.proxy

    Add to PowerShell profile so it runs automatically on every new terminal:
        . "$env:USERPROFILE\scripts\set_git_proxy.ps1"
    Or call manually before git operations.

.EXAMPLE
    .\set_git_proxy.ps1
    .\set_git_proxy.ps1 -ProxyHost 10.10.10.190 -ProxyPort 3128 -TimeoutMs 1500
#>

param(
    [string]$ProxyHost  = '10.10.10.190',
    [int]   $ProxyPort  = 3128,
    [int]   $TimeoutMs  = 1500
)

function Test-ProxyReachable {
    param([string]$Hostname, [int]$Port, [int]$TimeoutMs)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $result = $tcp.BeginConnect($Hostname, $Port, $null, $null)
        $reachable = $result.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($reachable) { $tcp.EndConnect($result) }
        $tcp.Close()
        return $reachable
    } catch {
        return $false
    }
}

$proxyUrl = "http://${ProxyHost}:${ProxyPort}"

if (Test-ProxyReachable -Hostname $ProxyHost -Port $ProxyPort -TimeoutMs $TimeoutMs) {
    git config --global http.proxy  $proxyUrl
    git config --global https.proxy $proxyUrl
    Write-Host "[git-proxy] Proxy reachable — set http.proxy = $proxyUrl" -ForegroundColor Green
} else {
    git config --global --unset http.proxy  2>$null
    git config --global --unset https.proxy 2>$null
    Write-Host "[git-proxy] Proxy unreachable — http.proxy cleared (direct connection)" -ForegroundColor Yellow
}
