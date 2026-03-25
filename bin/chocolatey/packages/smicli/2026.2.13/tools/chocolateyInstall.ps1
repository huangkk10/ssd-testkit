# chocolateyInstall.ps1  smicli 2026.2.13 (v20260213C)
# Part of SSD TestKit offline Chocolatey package.
# Portable tool: copies SmiCli2.exe + kernel drivers (WinIo64.sys / WinIoEx.sys)
# from bin/installers/SmiCli/v20260213C/ and sets SMICLI_PATH machine-level env var.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$toolVersion = "v20260213C"
$installDir  = "C:\tools\SmiCli"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nPlease use bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$sourceDir = Join-Path $toolkitRoot "bin\installers\SmiCli\$toolVersion"
if (-not (Test-Path $sourceDir)) {
    throw "SmiCli source directory not found: $sourceDir`nExpected: bin/installers/SmiCli/$toolVersion/ under SSD_TESTKIT_ROOT."
}

$exePath = Join-Path $sourceDir "SmiCli2.exe"
if (-not (Test-Path $exePath)) {
    throw "SmiCli2.exe not found: $exePath"
}

Write-Host "Installing SmiCli2 ($toolVersion) to $installDir ..."

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

[Environment]::SetEnvironmentVariable('SMICLI_PATH', "$installDir\SmiCli2.exe", 'Machine')
Write-Host "SMICLI_PATH set to $installDir\SmiCli2.exe"
Write-Host "SmiCli2 ($toolVersion) installed successfully."
