# chocolateyInstall.ps1  git 2.44.0
# Part of SSD TestKit offline Chocolatey package.
# Type A installer: runs Git silent installer (Inno Setup).
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$toolVersion  = "2.44.0"
$installerExe = "Git-2.44.0-64-bit.exe"
$installDir   = "C:\Program Files\Git"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nPlease use bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$installer = Join-Path $toolkitRoot "bin\installers\git\$toolVersion\$installerExe"
if (-not (Test-Path $installer)) {
    throw "Git installer not found: $installer"
}

Write-Host "Installing Git $toolVersion ..."
Write-Host "Installer: $installer"

$proc = Start-Process -FilePath $installer `
    -ArgumentList "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES /NOCANCEL" `
    -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw "Git installer failed with exit code: $($proc.ExitCode)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning "Git installed successfully. A system reboot is required to complete installation."
} else {
    Write-Host "Git $toolVersion installed successfully."
}
