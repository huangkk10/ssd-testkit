$pythonVersion = "3.10.11"
$installerExe = "python-3.10.11-amd64.exe"
$toolkitRoot = $env:SSD_TESTKIT_ROOT
$installDir = "C:\Program Files\Python310"

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT is not set. Run via install_packages.ps1 or set it manually."
}

$installer = Join-Path $toolkitRoot "bin\installers\python_installer\$pythonVersion\$installerExe"
if (-not (Test-Path $installer)) {
    throw "Installer not found: $installer"
}

Write-Host "Python installer: $installer"
Write-Host "Installing Python $pythonVersion ..."

$arguments = @(
    "/quiet"
    "InstallAllUsers=1"
    "PrependPath=1"
    "Include_test=0"
    "TargetDir=$installDir"
)

$proc = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw "Python installer failed with exit code: $($proc.ExitCode)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning "Python $pythonVersion installed successfully. A system reboot is required to complete installation."
} else {
    Write-Host "Python $pythonVersion installed successfully."
}