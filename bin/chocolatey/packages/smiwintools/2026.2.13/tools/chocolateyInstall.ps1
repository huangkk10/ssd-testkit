# chocolateyInstall.ps1  smiwintools 2026.2.13 (SmiWinTools_v20260213B)
# Part of SSD TestKit offline Chocolatey package.
# Portable tool: copies the entire SmiWinTools directory tree from
# bin/installers/SmiWinTools/v20260213B/ and sets SMIWINTOOLS_PATH machine-level env var.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.

$toolVersion = "v20260213B"
$installDir  = "C:\tools\SmiWinTools"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nPlease use bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$sourceDir = Join-Path $toolkitRoot "bin\installers\SmiWinTools\$toolVersion"
if (-not (Test-Path $sourceDir)) {
    throw "SmiWinTools source directory not found: $sourceDir`nExpected: bin/installers/SmiWinTools/$toolVersion/ under SSD_TESTKIT_ROOT."
}

Write-Host "Installing SmiWinTools ($toolVersion) to $installDir ..."

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

if (-not (Test-Path "$installDir\SmartCheck.bat")) {
    throw "Copy failed: SmartCheck.bat not found at $installDir"
}

# Set SMIWINTOOLS_PATH machine-level env var pointing to the install directory
[Environment]::SetEnvironmentVariable('SMIWINTOOLS_PATH', $installDir, 'Machine')
Write-Host "Set SMIWINTOOLS_PATH = $installDir (Machine scope)"

Write-Host "SmiWinTools ($toolVersion) installed successfully."
