# chocolateyUninstall.ps1  git 2.44.0

$installDir = "C:\Program Files\Git"

Write-Host "Uninstalling Git ..."

$uninstaller = Join-Path $installDir "unins000.exe"
if (Test-Path $uninstaller) {
    $proc = Start-Process -FilePath $uninstaller -ArgumentList "/VERYSILENT /NORESTART" -Wait -PassThru
    if ($proc.ExitCode -notin @(0, 3010)) {
        Write-Warning "Git uninstaller returned exit code: $($proc.ExitCode)"
    } else {
        Write-Host "Git uninstalled successfully."
    }
} else {
    Write-Warning "Uninstaller not found at $uninstaller — removing install directory manually."
    if (Test-Path $installDir) {
        Remove-Item $installDir -Recurse -Force
        Write-Host "Removed $installDir"
    }
}
