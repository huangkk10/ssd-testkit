# chocolateyUninstall.ps1  smicli 2025.11.14 (SmiWinTools_v20251114A)
# Removes the SmiCli2 install directory and clears SMICLI_PATH env var.

$installDir = "C:\tools\SmiCli"

Write-Host "Uninstalling SmiCli2 from $installDir ..."

if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
    Write-Host "Removed $installDir"
} else {
    Write-Host "Directory not found (already removed?): $installDir"
}

$current = [Environment]::GetEnvironmentVariable('SMICLI_PATH', 'Machine')
if ($current) {
    [Environment]::SetEnvironmentVariable('SMICLI_PATH', $null, 'Machine')
    Write-Host "Cleared SMICLI_PATH (was: $current)"
} else {
    Write-Host "SMICLI_PATH was not set, nothing to clear."
}

Write-Host "SmiCli2 uninstalled successfully."
