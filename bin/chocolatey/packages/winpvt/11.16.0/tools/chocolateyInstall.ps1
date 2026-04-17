# chocolateyInstall.ps1  winpvt 11.16.0

$toolVersion  = "11.16.0"
$installerExe = "WinPVT.exe"
$installDir   = "C:\Program Files\HP\WinPVT"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

Write-Host "Installing WinPVT $toolVersion ..."

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\winpvt\$toolVersion"
    $installer = Join-Path $sourceDir $installerExe
    if (-not (Test-Path $installer)) {
        throw "Installer not found: $installer"
    }
} else {
    throw "SSD_TESTKIT_ROOT is not set. Cannot locate WinPVT installer."
}

# NOTE: WinPVT (HP) uses /quiet for silent install.
# If installation fails, verify the correct silent flag with: WinPVT.exe /?
$proc = Start-Process -FilePath $installer `
    -ArgumentList "/quiet" `
    -Wait -PassThru
if ($proc.ExitCode -notin @(0, 3010)) {
    throw "WinPVT installer failed with exit code: $($proc.ExitCode)"
}

Write-Host "WinPVT $toolVersion installed to $installDir"
