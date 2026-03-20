# chocolateyInstall.ps1  burnin 10.2.1004

$toolVersion  = "10.2.1004"
$installerExe = "bitwindows.exe"
$installDir   = "C:\Program Files\BurnInTest"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

Write-Host "Installing BurnInTest $toolVersion ..."

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT is not set. Cannot locate BurnInTest installer."
}

$installer = Join-Path $toolkitRoot "bin\installers\BurnIn\$toolVersion\$installerExe"
if (-not (Test-Path $installer)) {
    throw "Installer not found: $installer"
}

# Run Inno Setup silent install
$proc = Start-Process -FilePath $installer `
    -ArgumentList "/SILENT /SUPPRESSMSGBOXES /NORESTART /DIR=`"$installDir`"" `
    -Wait -PassThru
if ($proc.ExitCode -notin @(0, 3010)) {
    throw "BurnInTest installer failed with exit code: $($proc.ExitCode)"
}

# Copy Configs and key.dat from source alongside installer
$sourceDir = Join-Path $toolkitRoot "bin\installers\BurnIn\$toolVersion"
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

# Set BURNIN_PATH to the install directory (bit.exe lives there)
[Environment]::SetEnvironmentVariable('BURNIN_PATH', $installDir, 'Machine')
Write-Host "Set BURNIN_PATH = $installDir (Machine scope)"

if ($proc.ExitCode -eq 3010) {
    Write-Warning "BurnInTest installed successfully but a reboot is required."
} else {
    Write-Host "BurnInTest $toolVersion installed successfully."
}
