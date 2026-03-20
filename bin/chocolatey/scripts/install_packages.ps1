# install_packages.ps1
# Read packages.config and batch install all packages according to active_source.
#
# Usage:
#   .\install_packages.ps1
#   .\install_packages.ps1 -ConfigDir "D:\offline\choco\config"
#   .\install_packages.ps1 -Source "C:\mypackages"   # Override source path

param(
    [string]$ConfigDir = "$PSScriptRoot\..\config",
    [string]$Source    = ""    # Override the path corresponding to active_source in environment.config
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Ensure choco is installed ───────────────────────────────────────────────
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Error "'choco' command not found. Please run install_choco.ps1 to install Chocolatey first."
    exit 1
}

# ── Read packages.config ─────────────────────────────────────────────────────
$pkgConfig = Join-Path $ConfigDir "packages.config"
if (-not (Test-Path $pkgConfig)) {
    Write-Error "packages.config not found: $pkgConfig"
    exit 1
}
[xml]$pkgXml = Get-Content $pkgConfig
$packages = $pkgXml.packages.package | Where-Object { $_ -ne $null }
if (-not $packages) {
    Write-Host "[INFO] No packages found in packages.config, skipping installation."
    exit 0
}

# ── Determine --source parameter ─────────────────────────────────────────────
$chocoArgs = @("install", "--yes", "--no-progress", "--ignore-checksums")
if ($Source -ne "") {
    $chocoArgs += "--source"
    $chocoArgs += $Source
}

# ── Install each package in order ───────────────────────────────────────────
$failed = @()
foreach ($pkg in $packages) {
    $id  = $pkg.id
    $ver = $pkg.version
    Write-Host "`n[PKG] Installing $id $ver ..."

    $args = $chocoArgs + @($id, "--version", $ver)
    & choco @args
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[WARN] $id $ver installation returned exit code $LASTEXITCODE"
        $failed += "$id@$ver"
    } else {
        Write-Host "[OK]  $id $ver installed."
    }
}

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host "`n============================================"
$total = @($packages).Count
Write-Host " Total  : $total"
Write-Host " Success: $($total - $failed.Count)"
Write-Host " Failed : $($failed.Count)"
if ($failed.Count -gt 0) {
    Write-Warning " Failed packages: $($failed -join ', ')"
    exit 1
}
Write-Host "============================================"
