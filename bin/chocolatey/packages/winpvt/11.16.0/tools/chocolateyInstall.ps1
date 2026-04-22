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

# WinPVT.exe is an InstallShield EXE wrapper around an MSI.
# InstallShield EXE flags:
#   /s              — suppress the outer extraction UI (silent mode for the EXE launcher)
#   /v"..."         — pass the quoted string as arguments directly to msiexec
# msiexec flags (inside /v):
#   /qn             — quiet, no UI
#   REBOOT=ReallySuppress — MSI property: absolutely no reboot (stronger than /norestart)
#   /norestart      — Windows Installer flag for no reboot
# Reboot is handled centrally by test_04_clean_environment.
# Exit 3010 = success but reboot pending; treated as success.
$proc = Start-Process -FilePath $installer `
    -ArgumentList '/s /v"/qn REBOOT=ReallySuppress /norestart"' `
    -Wait -PassThru
if ($proc.ExitCode -notin @(0, 3010)) {
    throw "WinPVT installer failed with exit code: $($proc.ExitCode)"
}

Write-Host "WinPVT $toolVersion installed to $installDir"
