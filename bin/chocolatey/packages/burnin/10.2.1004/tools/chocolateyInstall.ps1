# chocolateyInstall.ps1  burnin 10.2.1004

$toolVersion  = "10.2.1004"
$installerExe = "bitwindows.exe"
$installDir   = "C:\Program Files\BurnInTest"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

Write-Host "Installing BurnInTest $toolVersion ..."

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\BurnIn\$toolVersion"
    $installer = Join-Path $sourceDir $installerExe
    if (-not (Test-Path $installer)) {
        throw "Installer not found: $installer"
    }
} else {
    $nexusBase = "https://nexus.internal/repository/raw-windows-tools"
    $zip       = "$env:TEMP\BurnIn-$toolVersion.zip"
    $sourceDir = "$env:TEMP\BurnIn-$toolVersion"
    Write-Host "Downloading BurnInTest from Nexus ..."
    iwr "$nexusBase/BurnIn/$toolVersion/BurnIn-$toolVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $sourceDir) { Remove-Item $sourceDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $sourceDir -Force
    $installer = Join-Path $sourceDir $installerExe
    if (-not (Test-Path $installer)) {
        throw "Installer not found after download: $installer"
    }
}

# Run Inno Setup silent install
$proc = Start-Process -FilePath $installer `
    -ArgumentList "/SILENT /SUPPRESSMSGBOXES /NORESTART /DIR=`"$installDir`"" `
    -Wait -PassThru
if ($proc.ExitCode -notin @(0, 3010)) {
    throw "BurnInTest installer failed with exit code: $($proc.ExitCode)"
}

# Copy Configs and key.dat from source alongside installer
$configsSrc = Join-Path $sourceDir "Configs"
$keyDatSrc  = Join-Path $sourceDir "key.dat"

if (Test-Path $configsSrc) {
    Copy-Item -Path $configsSrc -Destination $installDir -Recurse -Force
    Write-Host "Copied Configs/ to $installDir"
}
if (Test-Path $keyDatSrc) {
    Copy-Item -Path $keyDatSrc -Destination $installDir -Force
    Write-Host "Copied key.dat to $installDir"
}

[Environment]::SetEnvironmentVariable('BURNIN_PATH', $installDir, 'Machine')
Write-Host "Set BURNIN_PATH = $installDir (Machine scope)"

if ($proc.ExitCode -eq 3010) {
    Write-Warning "BurnInTest installed successfully but a reboot is required."
} else {
    Write-Host "BurnInTest $toolVersion installed successfully."
}
