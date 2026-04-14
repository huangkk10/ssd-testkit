# chocolateyInstall.ps1  git 2.44.0
# Part of SSD TestKit offline Chocolatey package.
# Type A installer: runs Git silent installer (Inno Setup).

$toolVersion  = "2.44.0"
$installerExe = "Git-2.44.0-64-bit.exe"
$installDir   = "C:\Program Files\Git"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $installer = Join-Path $toolkitRoot "bin\installers\git\$toolVersion\$installerExe"
    if (-not (Test-Path $installer)) {
        throw "Git installer not found: $installer"
    }
} else {
    $nexusBase  = "https://nexus.internal/repository/raw-windows-tools"
    $zip        = "$env:TEMP\git-$toolVersion.zip"
    $extractDir = "$env:TEMP\git-$toolVersion"
    Write-Host "Downloading Git from Nexus ..."
    iwr "$nexusBase/git/$toolVersion/git-$toolVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $extractDir -Force
    $installer = Join-Path $extractDir $installerExe
    if (-not (Test-Path $installer)) {
        throw "Git installer not found after download: $installer"
    }
}

Write-Host "Installing Git $toolVersion ..."
Write-Host "Installer: $installer"

$proc = Start-Process -FilePath $installer `
    -ArgumentList "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES /NOCANCEL" `
    -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw "Git installer failed with exit code: $($proc.ExitCode)"
}

if ($proc.ExitCode -eq 3010) {
    Write-Warning "Git installed successfully. A system reboot is required to complete installation."
} else {
    Write-Host "Git $toolVersion installed successfully."
}
