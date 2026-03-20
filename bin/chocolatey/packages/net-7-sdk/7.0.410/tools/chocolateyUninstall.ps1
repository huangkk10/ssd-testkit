$sdkVersion  = "7.0.410"
$installerExe = "dotnet-sdk-$sdkVersion-win-x64.exe"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT is not set. Run via install_packages.ps1 or set it manually."
}

$installer = Join-Path $toolkitRoot "bin\installers\net_7_sdk\$sdkVersion\$installerExe"
if (-not (Test-Path $installer)) {
    throw "Installer not found: $installer"
}

Write-Host "Uninstalling .NET 7 SDK $sdkVersion..."

$proc = Start-Process -FilePath $installer -ArgumentList "/uninstall /quiet /norestart" -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw ".NET 7 SDK uninstaller failed with exit code: $($proc.ExitCode)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning ".NET 7 SDK uninstalled. A system reboot is required to complete removal."
} else {
    Write-Host ".NET 7 SDK $sdkVersion uninstalled successfully."
}
