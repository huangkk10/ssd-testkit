# chocolateyUninstall.ps1  windows-adk 26100 (Win11 24H2)
# Calls adksetup.exe /uninstall to remove all installed ADK features.

$buildNumber = "26100"
$toolkitRoot = $env:SSD_TESTKIT_ROOT
if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set."
}

$installer = Join-Path $toolkitRoot "bin\installers\WindowsADK\$buildNumber\adksetup.exe"
if (-not (Test-Path $installer)) {
    throw "Windows ADK installer not found: $installer"
}

Write-Host "Uninstalling Windows ADK Build $buildNumber ..."
$proc = Start-Process `
    -FilePath $installer `
    -ArgumentList "/quiet /norestart /uninstall" `
    -Wait -PassThru

if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
    throw "adksetup.exe /uninstall exited with code $($proc.ExitCode)"
}
Write-Host "Windows ADK Build $buildNumber uninstalled (ExitCode: $($proc.ExitCode))"
