# chocolateyUninstall.ps1  playwright-browsers 1.58.0
# Removes the Playwright browser install directory and clears PLAYWRIGHT_BROWSERS_PATH.

$installDir = "C:\tools\playwright-browsers"

Write-Host "Uninstalling Playwright browsers from $installDir ..."

if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
    Write-Host "Removed $installDir"
} else {
    Write-Host "Directory not found (already removed?): $installDir"
}

$current = [Environment]::GetEnvironmentVariable('PLAYWRIGHT_BROWSERS_PATH', 'Machine')
if ($current) {
    [Environment]::SetEnvironmentVariable('PLAYWRIGHT_BROWSERS_PATH', $null, 'Machine')
    Write-Host "Cleared PLAYWRIGHT_BROWSERS_PATH (was: $current)"
} else {
    Write-Host "PLAYWRIGHT_BROWSERS_PATH was not set, nothing to clear."
}

Write-Host "Playwright browsers uninstalled successfully."
