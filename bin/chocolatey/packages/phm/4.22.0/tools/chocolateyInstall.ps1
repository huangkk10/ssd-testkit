# chocolateyInstall.ps1  phm 4.22.0 (PHM V4.22.0_B25.02.06.02_H)
# Part of SSD TestKit offline Chocolatey package.
# Type A installer: runs the PHM silent installer and sets PHM_PATH env var.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$toolVersion  = "V4.22.0_B25.02.06.02_H"
$installerExe = "phm_nda_$toolVersion.exe"
$installDir   = "C:\Program Files\PowerhouseMountain"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nPlease use bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$installer = Join-Path $toolkitRoot "bin\installers\PHM\$toolVersion\$installerExe"
if (-not (Test-Path $installer)) {
    throw "PHM installer not found: $installer"
}

Write-Host "Installing PHM $toolVersion ..."
Write-Host "Installer: $installer"

$proc = Start-Process -FilePath $installer -ArgumentList "/S" -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw "PHM installer failed with exit code: $($proc.ExitCode)"
}

# Locate installed PHM executable and set PHM_PATH
$phmExe = Get-ChildItem -Path $installDir -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -match "PHM|PowerhouseMountain|Powerhouse" } |
          Select-Object -First 1

if ($phmExe) {
    [Environment]::SetEnvironmentVariable('PHM_PATH', $phmExe.FullName, 'Machine')
    Write-Host "Set PHM_PATH = $($phmExe.FullName) (Machine scope)"
} else {
    # Fallback: set to install directory
    [Environment]::SetEnvironmentVariable('PHM_PATH', $installDir, 'Machine')
    Write-Host "Set PHM_PATH = $installDir (Machine scope, exe not found)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning "PHM installed successfully. A system reboot is required to complete installation."
} else {
    Write-Host "PHM $toolVersion installed successfully."
}
