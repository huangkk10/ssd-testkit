# chocolateyUninstall.ps1  phm 4.22.0 (PHM V4.22.0_B25.02.06.02_H)

$toolVersion  = "V4.22.0_B25.02.06.02_H"
$installerExe = "phm_nda_$toolVersion.exe"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

Write-Host "Uninstalling PHM $toolVersion ..."

if ($toolkitRoot) {
    $installer = Join-Path $toolkitRoot "bin\installers\PHM\$toolVersion\$installerExe"
    if (Test-Path $installer) {
        $proc = Start-Process -FilePath $installer -ArgumentList "/S /uninstall" -Wait -PassThru
        if ($proc.ExitCode -notin @(0, 3010)) {
            Write-Warning "PHM uninstaller returned exit code: $($proc.ExitCode)"
        }
    } else {
        Write-Warning "Installer not found for silent uninstall: $installer"
        Write-Warning "Attempting to remove install directory manually."
        $installDir = "C:\Program Files\PowerhouseMountain"
        if (Test-Path $installDir) {
            Remove-Item $installDir -Recurse -Force
            Write-Host "Removed $installDir"
        }
    }
} else {
    Write-Warning "SSD_TESTKIT_ROOT not set - removing install directory manually."
    $installDir = "C:\Program Files\PowerhouseMountain"
    if (Test-Path $installDir) {
        Remove-Item $installDir -Recurse -Force
        Write-Host "Removed $installDir"
    }
}

[Environment]::SetEnvironmentVariable('PHM_PATH', $null, 'Machine')
Write-Host "PHM uninstalled. PHM_PATH cleared."
