# bootstrap.ps1
# One-click bootstrap script: Install Chocolatey → Set offline source → Batch install all packages
#
# Usage (run under bin/chocolatey/installer/ in the release package):
#   .\bootstrap.ps1
#   .\bootstrap.ps1 -Source nexus        # Switch to Nexus source
#   .\bootstrap.ps1 -SkipInstallChoco    # Skip install step if Choco is already installed

param(
    [string]$Source        = "",          # Override active_source in environment.config
    [switch]$SkipInstallChoco = $false,
    [switch]$SkipVerify       = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir  = $PSScriptRoot                              # bin/chocolatey/installer/
$ChocoRoot  = Split-Path $ScriptDir -Parent              # bin/chocolatey/
$ScriptsDir = Join-Path $ChocoRoot "scripts"
$ConfigDir  = Join-Path $ChocoRoot "config"

Write-Host "============================================"
Write-Host " SSD-Testkit Chocolatey Bootstrap"
Write-Host " Root : $ChocoRoot"
Write-Host "============================================"

# ── Step 1: Install Chocolatey ─────────────────────────────────────────────
if (-not $SkipInstallChoco) {
    Write-Host "`n[Step 1] Installing Chocolatey ..."
    & "$ScriptsDir\install_choco.ps1"
} else {
    Write-Host "`n[Step 1] Skipped (SkipInstallChoco)"
}

# ── Step 2: Load environment.config and determine source ────────────────────
Write-Host "`n[Step 2] Loading environment config ..."
$envCfg     = Join-Path $ConfigDir "environment.config"
$activeSource = "offline"   # default
if (Test-Path $envCfg) {
    $cfgContent = Get-Content $envCfg -Raw
    $m = [regex]::Match($cfgContent, 'active_source:\s*(\S+)')
    if ($m.Success) { $activeSource = $m.Groups[1].Value }
}
if ($Source -ne "") { $activeSource = $Source }   # parameter override
Write-Host "         active_source = $activeSource"

# ── Step 3: Determine choco --source path ───────────────────────────────────
$srcCfg = Join-Path $ConfigDir "sources.config"
$chocoSource = ""
if ($activeSource -eq "offline") {
    # Convert relative path to absolute path (relative to project root, i.e., parent of bin/)
    $projectRoot = Split-Path (Split-Path $ChocoRoot -Parent) -Parent
    $chocoSource = Join-Path $projectRoot "bin\chocolatey\packages"
} elseif (Test-Path $srcCfg) {
    $srcContent = Get-Content $srcCfg -Raw
    $urlMatch   = [regex]::Match($srcContent, "(?s)${activeSource}:.*?url:\s*['""]?([^\s'`"]+)")
    $pathMatch  = [regex]::Match($srcContent, "(?s)${activeSource}:.*?path:\s*['""]?([^\s'`"#]+)")
    if ($urlMatch.Success)  { $chocoSource = $urlMatch.Groups[1].Value.Trim() }
    elseif ($pathMatch.Success) { $chocoSource = $pathMatch.Groups[1].Value.Trim() }
}
Write-Host "         choco source  = $chocoSource"

# ── Step 4: Install all packages ────────────────────────────────────────────
Write-Host "`n[Step 3] Installing packages ..."
& "$ScriptsDir\install_packages.ps1" -ConfigDir $ConfigDir -Source $chocoSource

# ── Step 5: Verification (optional) ─────────────────────────────────────────
if (-not $SkipVerify) {
    Write-Host "`n[Step 4] Verifying packages ..."
    $verifyScript = Join-Path $ScriptsDir "verify_packages.ps1"
    if (Test-Path $verifyScript) {
        & $verifyScript -ConfigDir $ConfigDir
    } else {
        Write-Host "         (verify_packages.ps1 not yet available, skipped)"
    }
}

Write-Host "`n============================================"
Write-Host " Bootstrap completed."
Write-Host "============================================"
