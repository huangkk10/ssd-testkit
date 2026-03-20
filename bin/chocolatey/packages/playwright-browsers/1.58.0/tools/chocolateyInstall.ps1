# chocolateyInstall.ps1  playwright-browsers 1.58.0
# Portable tool: copies Playwright browser binaries to $installDir
# and sets PLAYWRIGHT_BROWSERS_PATH machine-level env var.
# Requires: $env:SSD_TESTKIT_ROOT pointing to the ssd-testkit repo root.
#
# Browser builds included:
#   chromium-1208, chromium_headless_shell-1208, ffmpeg-1011, winldd-1007

$playwrightVersion = "1.58.0"
$installDir        = "C:\tools\playwright-browsers"
$toolkitRoot       = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT environment variable is not set.`nUse bin/chocolatey/scripts/install_packages.ps1 instead of calling choco directly."
}

$sourceDir = Join-Path $toolkitRoot "bin\installers\playwright-browsers\$playwrightVersion"
if (-not (Test-Path $sourceDir)) {
    throw "Playwright browsers source directory not found: $sourceDir`nExpected: bin/installers/playwright-browsers/$playwrightVersion/ under SSD_TESTKIT_ROOT."
}

# Verify at least one browser build is present
$chromiumDir = Join-Path $sourceDir "chromium-1208"
if (-not (Test-Path $chromiumDir)) {
    throw "chromium-1208 not found under $sourceDir"
}

Write-Host "Installing Playwright browsers ($playwrightVersion) to $installDir ..."

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

# Copy entire browser directory tree (preserves chromium-1208/, ffmpeg-1011/, etc.)
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

# Verify copy succeeded
$destChromium = Join-Path $installDir "chromium-1208\chrome-win64\chrome.exe"
if (-not (Test-Path $destChromium)) {
    throw "Copy failed: chrome.exe not found at $destChromium"
}

# Set PLAYWRIGHT_BROWSERS_PATH so Playwright finds browsers without additional config
[Environment]::SetEnvironmentVariable('PLAYWRIGHT_BROWSERS_PATH', $installDir, 'Machine')
Write-Host "Set PLAYWRIGHT_BROWSERS_PATH = $installDir (Machine scope)"

Write-Host "Playwright browsers ($playwrightVersion) installed successfully."
