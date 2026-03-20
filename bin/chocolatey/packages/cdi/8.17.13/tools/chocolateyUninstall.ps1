$installDir = "C:\tools\CrystalDiskInfo"

Write-Host "Uninstalling CrystalDiskInfo..."
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
    Write-Host "Removed $installDir"
}

[Environment]::SetEnvironmentVariable('CDI_PATH', $null, 'Machine')
Write-Host "CrystalDiskInfo uninstalled. CDI_PATH cleared."
