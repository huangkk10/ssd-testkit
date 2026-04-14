# chocolateyInstall.ps1  smiwintools 2026.2.13 (SmiWinTools_v20260213B)
# Part of SSD TestKit offline Chocolatey package.
# Portable tool: copies the entire SmiWinTools directory tree.

$toolVersion = "v20260213B"
$installDir  = "C:\tools\SmiWinTools"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\SmiWinTools\$toolVersion"
    if (-not (Test-Path $sourceDir)) {
        throw "SmiWinTools source directory not found: $sourceDir`nExpected: bin/installers/SmiWinTools/$toolVersion/ under SSD_TESTKIT_ROOT."
    }
} else {
    $nexusBase = "https://nexus.internal/repository/raw-windows-tools"
    $zip       = "$env:TEMP\SmiWinTools-$toolVersion.zip"
    $sourceDir = "$env:TEMP\SmiWinTools-$toolVersion"
    Write-Host "Downloading SmiWinTools from Nexus ..."
    iwr "$nexusBase/SmiWinTools/$toolVersion/SmiWinTools-$toolVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $sourceDir) { Remove-Item $sourceDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $sourceDir -Force
}

Write-Host "Installing SmiWinTools ($toolVersion) to $installDir ..."

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

if (-not (Test-Path "$installDir\SmartCheck.bat")) {
    throw "Copy failed: SmartCheck.bat not found at $installDir"
}

[Environment]::SetEnvironmentVariable('SMIWINTOOLS_PATH', $installDir, 'Machine')
Write-Host "Set SMIWINTOOLS_PATH = $installDir (Machine scope)"

Write-Host "SmiWinTools ($toolVersion) installed successfully."
