# chocolateyInstall.ps1  windows-adk 26100 (Win11 24H2)
# Part of SSD TestKit offline Chocolatey package.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$buildNumber  = "26100"
$toolkitRoot  = $env:SSD_TESTKIT_ROOT
if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nPlease use bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$installer = Join-Path $toolkitRoot "bin\installers\WindowsADK\$buildNumber\adksetup.exe"
if (-not (Test-Path $installer)) {
    throw "Windows ADK installer not found: $installer`nExpected: bin/installers/WindowsADK/$buildNumber/adksetup.exe under SSD_TESTKIT_ROOT."
}

Write-Host "Installing Windows ADK Build $buildNumber (Win11 24H2)..."
Write-Host "Installer: $installer"

$proc = Start-Process `
    -FilePath $installer `
    -ArgumentList "/quiet /norestart /features OptionId.WindowsPerformanceToolkit OptionId.WindowsAssessmentToolkit" `
    -Wait -PassThru

# 3010 = reboot required (acceptable for ADK)
if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
    throw "adksetup.exe exited with code $($proc.ExitCode)"
}
Write-Host "Windows ADK Build $buildNumber installed successfully (ExitCode: $($proc.ExitCode))"
