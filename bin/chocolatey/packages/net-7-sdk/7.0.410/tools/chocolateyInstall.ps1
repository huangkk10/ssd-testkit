# chocolateyInstall.ps1  net-7-sdk 7.0.410

$sdkVersion   = "7.0.410"
$installerExe = "dotnet-sdk-$sdkVersion-win-x64.exe"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $installer = Join-Path $toolkitRoot "bin\installers\net_7_sdk\$sdkVersion\$installerExe"
    if (-not (Test-Path $installer)) {
        throw "Installer not found: $installer"
    }
} else {
    $nexusBase  = "https://nexus.internal/repository/raw-windows-tools"
    $zip        = "$env:TEMP\net-7-sdk-$sdkVersion.zip"
    $extractDir = "$env:TEMP\net-7-sdk-$sdkVersion"
    Write-Host "Downloading .NET 7 SDK from Nexus ..."
    iwr "$nexusBase/net_7_sdk/$sdkVersion/net-7-sdk-$sdkVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $extractDir -Force
    $installer = Join-Path $extractDir $installerExe
    if (-not (Test-Path $installer)) {
        throw "Installer not found after download: $installer"
    }
}

Write-Host ".NET 7 SDK installer: $installer"
Write-Host "Installing .NET 7 SDK $sdkVersion (this may take a few minutes)..."

$proc = Start-Process -FilePath $installer -ArgumentList "/install /quiet /norestart" -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw ".NET 7 SDK installer failed with exit code: $($proc.ExitCode)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning ".NET 7 SDK installed successfully. A system reboot is required to complete installation."
} else {
    Write-Host ".NET 7 SDK $sdkVersion installed successfully."
}
