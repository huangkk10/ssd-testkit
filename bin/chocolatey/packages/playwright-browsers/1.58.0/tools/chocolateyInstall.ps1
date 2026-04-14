# chocolateyInstall.ps1  playwright-browsers 1.58.0
# Portable tool: copies Playwright browser binaries to $installDir
# and sets PLAYWRIGHT_BROWSERS_PATH machine-level env var.
#
# Browser builds included:
#   chromium-1208, chromium_headless_shell-1208, ffmpeg-1011, winldd-1007

$playwrightVersion = "1.58.0"
$installDir        = "C:\tools\playwright-browsers"
$toolkitRoot       = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\playwright-browsers\$playwrightVersion"
    if (-not (Test-Path $sourceDir)) {
        throw "Playwright browsers source directory not found: $sourceDir`nExpected: bin/installers/playwright-browsers/$playwrightVersion/ under SSD_TESTKIT_ROOT."
    }
    $chromiumDir = Join-Path $sourceDir "chromium-1208"
    if (-not (Test-Path $chromiumDir)) {
        throw "chromium-1208 not found under $sourceDir"
    }
} else {
    $nexusBase = "https://nexus.internal/repository/raw-windows-tools"
    $zip       = "$env:TEMP\playwright-browsers-$playwrightVersion.zip"
    $sourceDir = "$env:TEMP\playwright-browsers-$playwrightVersion"
    Write-Host "Downloading Playwright browsers from Nexus ..."
    iwr "$nexusBase/PlaywrightBrowsers/$playwrightVersion/playwright-browsers-$playwrightVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $sourceDir) { Remove-Item $sourceDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $sourceDir -Force
    $chromiumDir = Join-Path $sourceDir "chromium-1208"
    if (-not (Test-Path $chromiumDir)) {
        throw "chromium-1208 not found in downloaded archive"
    }
}

Write-Host "Installing Playwright browsers ($playwrightVersion) to $installDir ..."

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

$destChromium = Join-Path $installDir "chromium-1208\chrome-win64\chrome.exe"
if (-not (Test-Path $destChromium)) {
    throw "Copy failed: chrome.exe not found at $destChromium"
}

[Environment]::SetEnvironmentVariable('PLAYWRIGHT_BROWSERS_PATH', $installDir, 'Machine')
Write-Host "Set PLAYWRIGHT_BROWSERS_PATH = $installDir (Machine scope)"

Write-Host "Playwright browsers ($playwrightVersion) installed successfully."
