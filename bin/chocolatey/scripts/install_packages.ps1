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

# â”€â”€ Ensure choco is installed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Error "'choco' command not found. Please run install_choco.ps1 to install Chocolatey first."
    exit 1
}

# â”€â”€ Read packages.config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Set SSD_TESTKIT_ROOT so nupkg install scripts can locate large installers â”€â”€
# Scripts are at bin/chocolatey/scripts/ -> project root is 3 levels up
$env:SSD_TESTKIT_ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\")).Path
Write-Host "[INFO] SSD_TESTKIT_ROOT=$env:SSD_TESTKIT_ROOT"

# â”€â”€ Resolve base packages directory (for per-package source resolution) â”€â”€â”€â”€â”€â”€
# When $Source is not overridden, packages are stored at:
#   <project_root>/bin/chocolatey/packages/<id>/<version>/
# Chocolatey local folder source must point to the folder containing the nupkg;
# it does NOT recurse into subdirectories.
$packagesBaseDir = Join-Path $env:SSD_TESTKIT_ROOT "bin\chocolatey\packages"

# â”€â”€ Install each package in order â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$failed = @()
foreach ($pkg in $packages) {
    $id  = $pkg.id
    $ver = $pkg.version
    Write-Host "`n[PKG] Installing $id $ver ..."

    # Resolve the source: explicit override > per-package version folder > base dir
    if ($Source -ne "") {
        $pkgSource = $Source
    } else {
        $pkgSource = Join-Path $packagesBaseDir "$id\$ver"
        if (-not (Test-Path $pkgSource)) {
            Write-Warning "[WARN] Package source dir not found: $pkgSource"
            $failed += "$id@$ver"
            continue
        }
    }

    # NuGet normalises bare integers: e.g. "22621" -> "22621.0.0"
    # Pass the version as-is; choco will resolve it against what's in the nupkg.
    $args = @("install", $id, "--version", $ver, "--source", $pkgSource, "--yes", "--no-progress", "--ignore-checksums")
    & choco @args
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[WARN] $id $ver installation returned exit code $LASTEXITCODE"
        $failed += "$id@$ver"
    } else {
        Write-Host "[OK]  $id $ver installed."
    }
}

# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

