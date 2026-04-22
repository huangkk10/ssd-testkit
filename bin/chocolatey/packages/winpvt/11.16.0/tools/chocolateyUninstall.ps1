# chocolateyUninstall.ps1  winpvt 11.16.0

$toolVersion = "11.16.0"
$installDir  = "C:\Program Files\Hewlett-Packard\WinPVT 11.16.0"

Write-Host "Uninstalling WinPVT $toolVersion ..."

# Try standard Windows uninstall via registry
$uninstallKey = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" |
    Get-ItemProperty | Where-Object { $_.DisplayName -like "*WinPVT*" } | Select-Object -First 1

if ($uninstallKey -and $uninstallKey.UninstallString) {
    $uninstallStr = $uninstallKey.UninstallString

    # If MSI-based uninstaller, call msiexec directly so we can pass /norestart cleanly.
    # Reboot is handled centrally by test_04_clean_environment.
    if ($uninstallStr -match 'MsiExec|msiexec') {
        $guid = [regex]::Match($uninstallStr, '\{[^}]+\}').Value
        Write-Host "Running MSI uninstall: $guid"
        # REBOOT=ReallySuppress is the definitive MSI property to prevent any reboot.
        # /norestart alone is not sufficient — msiexec can still call InitiateShutdown.
        # Reboot is handled centrally by test_04_clean_environment.
        $proc = Start-Process -FilePath 'msiexec.exe' `
            -ArgumentList "/X$guid /quiet /norestart REBOOT=ReallySuppress" `
            -Wait -PassThru
    } else {
        Write-Host "Running EXE uninstaller: $uninstallStr"
        # Run the EXE directly (not via cmd.exe) so that /norestart and /quiet are
        # passed as actual arguments to the installer process.
        # Parse quoted or unquoted exe path from the registry UninstallString.
        if ($uninstallStr -match '^"([^"]+)"(.*)$') {
            $exePath  = $matches[1]
            $baseArgs = $matches[2].Trim()
        } else {
            $parts    = $uninstallStr -split ' ', 2
            $exePath  = $parts[0]
            $baseArgs = if ($parts.Count -gt 1) { $parts[1] } else { '' }
        }
        # Append common silent/no-restart flags; unrecognised flags are ignored by most installers.
        # /quiet  — InstallShield/Windows silent mode
        # /S      — NSIS silent mode
        # /NORESTART — Inno Setup no-restart flag
        # /norestart — MSI-style no-restart (for EXE wrappers around MSI)
        $silentArgs = '/quiet /norestart /S /NORESTART'
        $argStr     = if ($baseArgs) { "$baseArgs $silentArgs" } else { $silentArgs }
        $proc = Start-Process -FilePath $exePath `
            -ArgumentList $argStr `
            -Wait -PassThru
    }
    if ($proc.ExitCode -notin @(0, 3010)) {
        Write-Warning "WinPVT uninstaller returned exit code: $($proc.ExitCode)"
    }
} elseif (Test-Path $installDir) {
    Write-Warning "Uninstaller not found in registry - removing directory manually."
    Remove-Item $installDir -Recurse -Force
} else {
    Write-Warning "WinPVT not found at $installDir - skipping."
}

# Cancel any reboot that the WinPVT or WDTF uninstaller may have scheduled.
# Reboot is handled centrally by test_04_clean_environment.
Write-Host "Suppressing pending reboot (handled centrally by test_04_clean_environment)..."
& shutdown.exe /a 2>$null

Write-Host "WinPVT $toolVersion uninstalled."

# Exit 0: Chocolatey v2.x only accepts exit 0 from chocolateyUninstall.ps1 as success.
# Exit 3010 is only valid for install scripts; for uninstall, 3010 causes choco to
# mark the uninstall as failed and roll back the lib cache.
# Reboot is suppressed above (REBOOT=ReallySuppress + shutdown.exe /a) and will be
# handled centrally by test_04_clean_environment.
exit 0
