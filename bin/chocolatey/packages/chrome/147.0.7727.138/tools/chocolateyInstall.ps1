# chocolateyInstall.ps1  chrome 147.0.7727.138

$toolVersion = "147.0.7727.138"
$msiName     = "googlechromestandaloneenterprise64.msi"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

Write-Host "Installing Google Chrome $toolVersion ..."

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\chrome\$toolVersion"
    $installer = Join-Path $sourceDir $msiName
    if (-not (Test-Path $installer)) {
        throw "Chrome MSI not found: $installer"
    }
} else {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nUse bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

# Run MSI silent install
$proc = Start-Process -FilePath "msiexec.exe" `
    -ArgumentList "/i `"$installer`" /quiet /norestart" `
    -Wait -PassThru

if ($proc.ExitCode -notin @(0, 3010)) {
    throw "Chrome MSI installer failed with exit code: $($proc.ExitCode)"
}

$chromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
[Environment]::SetEnvironmentVariable('CHROME_PATH', $chromeExe, 'Machine')
Write-Host "Set CHROME_PATH = $chromeExe (Machine scope)"

if ($proc.ExitCode -eq 3010) {
    Write-Warning "Google Chrome installed successfully but a reboot is required."
} else {
    Write-Host "Google Chrome $toolVersion installed successfully."
}
