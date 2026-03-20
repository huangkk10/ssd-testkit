# chocolateyUninstall.ps1  burnin 10.2.1004

$toolVersion  = "10.2.1004"
$installerExe = "bitwindows.exe"
$installDir   = "C:\Program Files\BurnInTest"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

Write-Host "Uninstalling BurnInTest $toolVersion ..."

# Try Inno Setup silent uninstall via the bundled unins000.exe
$uninstaller = Join-Path $installDir "unins000.exe"
if (Test-Path $uninstaller) {
    $proc = Start-Process -FilePath $uninstaller `
        -ArgumentList "/SILENT /SUPPRESSMSGBOXES /NORESTART" `
        -Wait -PassThru
    if ($proc.ExitCode -notin @(0, 3010)) {
        Write-Warning "BurnInTest uninstaller returned exit code: $($proc.ExitCode)"
    }
} else {
    Write-Warning "Uninstaller not found at $uninstaller - removing directory manually."
    if (Test-Path $installDir) {
        Remove-Item $installDir -Recurse -Force
        Write-Host "Removed $installDir"
    }
}

[Environment]::SetEnvironmentVariable('BURNIN_PATH', $null, 'Machine')
Write-Host "BurnInTest uninstalled. BURNIN_PATH cleared."
