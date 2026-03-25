# chocolateyUninstall.ps1  smiwintools 2026.2.13.1 (SmiWinTools_v20260213C)

$installDir = "C:\tools\SmiWinTools"

Write-Host "Uninstalling SmiWinTools..."
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
    Write-Host "Removed $installDir"
}

[Environment]::SetEnvironmentVariable('SMIWINTOOLS_PATH', $null, 'Machine')
Write-Host "SmiWinTools uninstalled. SMIWINTOOLS_PATH cleared."
