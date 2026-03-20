# install_choco.ps1
# Offline install Chocolatey from local nupkg, no internet required.
#
# Usage:
#   .\install_choco.ps1
#   .\install_choco.ps1 -ChocoVersion 2.7.0
#   .\install_choco.ps1 -InstallerDir "D:\offline\choco\installer"

param(
    [string]$ChocoVersion = "2.7.0",
    [string]$InstallerDir = "$PSScriptRoot\..\installer"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── 1. Check if not already installed ───────────────────────────────────────
if (Get-Command choco -ErrorAction SilentlyContinue) {
    $installed = (choco --version 2>$null)
    Write-Host "[INFO] Chocolatey already installed: $installed"
    exit 0
}

# ── 2. Check if nupkg exists ────────────────────────────────────────────────
$nupkg = Join-Path $InstallerDir "chocolatey.$ChocoVersion.nupkg"
if (-not (Test-Path $nupkg)) {
    Write-Error "Chocolatey package not found: $nupkg`nPlease make sure the corresponding nupkg file exists under bin/chocolatey/installer/."
    exit 1
}

# ── 3. Extract nupkg (actually a zip) to temp directory ─────────────────────
$tempDir = Join-Path $env:TEMP "choco_install_$ChocoVersion"
Write-Host "[INFO] Extracting $nupkg to $tempDir ..."
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($nupkg, $tempDir)

# ── 4. Run install script ───────────────────────────────────────────────────
$installScript = Join-Path $tempDir "tools\chocolateyInstall.ps1"
if (-not (Test-Path $installScript)) {
    Write-Error "解壓後找不到安裝腳本：$installScript"
    exit 1
}

# chocolateyInstall.ps1 needs to know the source location of the nupkg
$env:ChocolateyInstallOverride = $null
$env:TEMP_CHOCO_NUPKG = $nupkg

Write-Host "[INFO] Running chocolateyInstall.ps1 ..."
Set-ExecutionPolicy Bypass -Scope Process -Force
& $installScript

# ── 5. Verify installation result ───────────────────────────────────────────
if (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Chocolatey $((choco --version)) installed successfully."
} else {
    Write-Error "Installation finished but 'choco' command not found. Please reopen PowerShell and try again."
    exit 1
}

# ── 6. 清理暫存 ─────────────────────────────────────────────────────────────
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[INFO] Temp directory cleaned."
