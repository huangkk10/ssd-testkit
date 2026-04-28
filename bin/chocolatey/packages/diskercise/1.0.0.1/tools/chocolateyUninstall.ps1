# chocolateyUninstall.ps1  diskercise 1.0.0.1

$installDir = "C:\tools\Diskercise"

Write-Host "Uninstalling Diskercise ..."
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
    Write-Host "Removed $installDir"
}

[Environment]::SetEnvironmentVariable('DISKERCISE_PATH', $null, 'Machine')
Write-Host "Diskercise uninstalled. DISKERCISE_PATH cleared."
