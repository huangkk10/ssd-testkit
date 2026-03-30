<#
.SYNOPSIS
  Install tools required by a test case via Chocolatey (from Nexus).

.PARAMETER TestCase
  Test case name, e.g. stc1685_burnin

.PARAMETER Force
  Re-install even if tool is already installed

.EXAMPLE
  .\tool-manager\prepare_testcase.ps1
  .\tool-manager\prepare_testcase.ps1 stc1685_burnin
  .\tool-manager\prepare_testcase.ps1 stc1685_burnin -Force
#>
param(
    [string]$TestCase = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root       = Split-Path $PSScriptRoot
$ChocoSource  = "https://nexus.internal/repository/choco-hosted"
$ChocoApiBase = "https://nexus.internal/repository/choco-hosted"

if (-not $TestCase) {
    $prepareYaml = Join-Path $PSScriptRoot "prepare.yaml"
    if (-not (Test-Path $prepareYaml)) { Write-Error "No TestCase specified and prepare.yaml not found at $prepareYaml"; exit 1 }
    $TestCase = python -c "import sys,yaml; print(yaml.safe_load(open(sys.argv[1],encoding='utf-8'))['testcase'])" $prepareYaml
}

Write-Host "TestCase: $TestCase" -ForegroundColor White
$TestCaseDir = Join-Path $Root "tests\integration\test_case\$TestCase"
$ToolsYaml   = Join-Path $TestCaseDir "Config\tools.yaml"
$Registry    = Join-Path $Root "lib\testtool\tools-registry.yaml"

if (-not (Test-Path $TestCaseDir)) { Write-Error "Test case dir not found: $TestCaseDir"; exit 1 }
if (-not (Test-Path $ToolsYaml))   { Write-Error "tools.yaml not found: $ToolsYaml"; exit 1 }
if (-not (Test-Path $Registry))    { Write-Error "tools-registry.yaml not found: $Registry"; exit 1 }

# Use Python to merge two YAMLs and return JSON
$pyScript = @"
import sys, yaml, json
with open(sys.argv[1], encoding='utf-8') as f:
    tools = yaml.safe_load(f).get('tools', [])
with open(sys.argv[2], encoding='utf-8') as f:
    registry = yaml.safe_load(f).get('tools', {})
result = []
for t in tools:
    tid = t['id']
    reg = registry.get(tid, {})
    install_dir = reg.get('install_dir', '')
    if not install_dir:
        continue
    binaries = reg.get('binaries', [])
    result.append({
        'id':          tid,
        'version':     reg.get('version', ''),
        'install_dir': install_dir,
        'binaries':    binaries,
    })
print(json.dumps(result))
"@

$entries = python -c $pyScript $ToolsYaml $Registry | ConvertFrom-Json

foreach ($entry in $entries) {
    # Step 1: 確保 nupkg 在 bin\chocolatey\packages\ (無論 binary 是否已安裝)
    $nupkgDir  = Join-Path $Root "bin\chocolatey\packages\$($entry.id)\$($entry.version)"
    $nupkgFile = Join-Path $nupkgDir "$($entry.id).$($entry.version).nupkg"

    if (-not (Test-Path $nupkgFile)) {
        $url = "$ChocoApiBase/$($entry.id)/$($entry.version)"
        Write-Host "  [DOWNLOAD] $($entry.id) $($entry.version)" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $nupkgDir -Force | Out-Null
        $cred = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:1.a"))
        Invoke-WebRequest -Uri $url -Headers @{Authorization="Basic $cred"} `
                          -OutFile $nupkgFile -UseBasicParsing
    }

    # Step 2: 確保 binary 已安裝
    $checkPath = if ($entry.binaries -and $entry.binaries.Count -gt 0) {
        Join-Path $entry.install_dir $entry.binaries[0]
    } else {
        $entry.install_dir
    }

    if ((Test-Path $checkPath) -and -not $Force) {
        Write-Host "  [SKIP] $($entry.id) ($checkPath)" -ForegroundColor DarkGray
        continue
    }

    Write-Host "  [INSTALL] $($entry.id)  source: $nupkgDir" -ForegroundColor Cyan
    $chocoArgs = @("install", $entry.id, "--source", $nupkgDir, "-y", "--no-progress")
    if ($Force) { $chocoArgs += "--force" }
    & choco @chocoArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "choco install $($entry.id) exited with code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Tools ready: $TestCase" -ForegroundColor Green
