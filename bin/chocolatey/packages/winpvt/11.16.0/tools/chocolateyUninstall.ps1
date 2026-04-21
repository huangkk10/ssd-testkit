# chocolateyUninstall.ps1  winpvt 11.16.0

$toolVersion = "11.16.0"
$installDir  = "C:\Program Files\Hewlett-Packard\WinPVT 11.16.0"

Write-Host "Uninstalling WinPVT $toolVersion ..."

# Try standard Windows uninstall via registry
$uninstallKey = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" |
    Get-ItemProperty | Where-Object { $_.DisplayName -like "*WinPVT*" } | Select-Object -First 1

if ($uninstallKey -and $uninstallKey.UninstallString) {
    $uninstallStr = $uninstallKey.UninstallString
    Write-Host "Running uninstaller: $uninstallStr"
    $proc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c `"$uninstallStr`" /quiet" `
        -Wait -PassThru
    if ($proc.ExitCode -notin @(0, 3010)) {
        Write-Warning "WinPVT uninstaller returned exit code: $($proc.ExitCode)"
    }
} elseif (Test-Path $installDir) {
    Write-Warning "Uninstaller not found in registry - removing directory manually."
    Remove-Item $installDir -Recurse -Force
} else {
    Write-Warning "WinPVT not found at $installDir - skipping."
}

Write-Host "WinPVT $toolVersion uninstalled."
