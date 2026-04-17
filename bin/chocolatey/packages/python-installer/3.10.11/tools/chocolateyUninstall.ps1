$pythonVersion = "3.10.11"
$installerExe = "python-3.10.11-amd64.exe"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT is not set. Run via install_packages.ps1 or set it manually."
}

$installer = Join-Path $toolkitRoot "bin\installers\python_installer\$pythonVersion\$installerExe"
if (-not (Test-Path $installer)) {
    throw "Installer not found: $installer"
}

Write-Host "Uninstalling Python $pythonVersion ..."

$arguments = @(
    "/quiet"
    "/uninstall"
)

$proc = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw "Python uninstaller failed with exit code: $($proc.ExitCode)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning "Python $pythonVersion uninstalled. A system reboot is required to complete removal."
} else {
    Write-Host "Python $pythonVersion uninstalled successfully."
}