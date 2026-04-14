# chocolateyInstall.ps1  windows-adk 26100 (Win11 24H2)
# Part of SSD TestKit offline Chocolatey package.

$buildNumber = "26100"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $installer = Join-Path $toolkitRoot "bin\installers\WindowsADK\$buildNumber\adksetup.exe"
    if (-not (Test-Path $installer)) {
        throw "Windows ADK installer not found: $installer`nExpected: bin/installers/WindowsADK/$buildNumber/adksetup.exe under SSD_TESTKIT_ROOT."
    }
} else {
    $nexusBase  = "https://nexus.internal/repository/raw-windows-tools"
    $zip        = "$env:TEMP\WindowsADK-$buildNumber.zip"
    $extractDir = "$env:TEMP\WindowsADK-$buildNumber"
    Write-Host "Downloading Windows ADK from Nexus ..."
    iwr "$nexusBase/WindowsADK/$buildNumber/WindowsADK-$buildNumber.0.0.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $extractDir -Force
    $installer = Join-Path $extractDir "adksetup.exe"
    if (-not (Test-Path $installer)) {
        throw "adksetup.exe not found after download: $installer"
    }
}

Write-Host "Installing Windows ADK Build $buildNumber (Win11 24H2)..."
Write-Host "Installer: $installer"

$proc = Start-Process `
    -FilePath $installer `
    -ArgumentList "/quiet /norestart /features OptionId.WindowsPerformanceToolkit OptionId.WindowsAssessmentToolkit" `
    -Wait -PassThru

if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
    throw "adksetup.exe exited with code $($proc.ExitCode)"
}
Write-Host "Windows ADK Build $buildNumber installed successfully (ExitCode: $($proc.ExitCode))"
