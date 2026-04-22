# chocolateyInstall.ps1  phm 4.22.0 (PHM V4.22.0_B25.02.06.02_H)
# Part of SSD TestKit offline Chocolatey package.
# Type A installer: runs the PHM silent installer and sets PHM_PATH env var.

$toolVersion  = "V4.22.0_B25.02.06.02_H"
$installerExe = "phm_nda_$toolVersion.exe"
$installDir   = "C:\Program Files\PowerhouseMountain"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $installer = Join-Path $toolkitRoot "bin\installers\PHM\$toolVersion\$installerExe"
    if (-not (Test-Path $installer)) {
        throw "PHM installer not found: $installer"
    }
} else {
    $nexusBase  = "https://nexus.internal/repository/raw-windows-tools"
    $zip        = "$env:TEMP\PHM-V4.22.0.zip"
    $extractDir = "$env:TEMP\PHM-V4.22.0"
    Write-Host "Downloading PHM from Nexus ..."
    iwr "$nexusBase/PHM/4.22.0/PHM-V4.22.0.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $extractDir -Force
    $installer = Join-Path $extractDir $installerExe
    if (-not (Test-Path $installer)) {
        throw "PHM installer not found after download: $installer"
    }
}

Write-Host "Installing PHM $toolVersion ..."
Write-Host "Installer: $installer"

# /norestart: suppress automatic reboot after install (NSIS flag).
# Reboot is handled centrally by test_04_clean_environment.
# exit code 3010 = success but reboot recommended; treated as normal.
$proc = Start-Process -FilePath $installer -ArgumentList "/S /norestart" -Wait -PassThru

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
    [Environment]::SetEnvironmentVariable('PHM_PATH', $installDir, 'Machine')
    Write-Host "Set PHM_PATH = $installDir (Machine scope, exe not found)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning "PHM installed successfully. A system reboot is required to complete installation."
} else {
    Write-Host "PHM $toolVersion installed successfully."
}
