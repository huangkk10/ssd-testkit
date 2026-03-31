<#
.SYNOPSIS
  Install tools required by a test case via Chocolatey (from Nexus).

.PARAMETER TestCase
  Test case name, e.g. stc1685_burnin

.EXAMPLE
  .\tool-manager\prepare_testcase.ps1
  .\tool-manager\prepare_testcase.ps1 stc1685_burnin
#>
param(
    [string]$TestCase = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root         = Split-Path $PSScriptRoot
$ChocoSource  = "https://10.252.170.171/repository/choco-hosted-nas"
$ChocoApiBase = "https://10.252.170.171/repository/choco-hosted-nas"
$NasZipBase   = "\\10.250.0.1\mdt\Team\PQ1-3\tool\ssd-testkit-source\windows\zip"

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
        'source_dir':  reg.get('source_dir', ''),
        'nexus_path':  reg.get('nexus_path', ''),
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
        & curl.exe -sk --ssl-no-revoke --noproxy $ChocoApiBase `
            -u "admin:1.a" -L -o $nupkgFile $url
        if ($LASTEXITCODE -ne 0) { Write-Warning "  [WARN] $($entry.id): nupkg download failed (curl exit $LASTEXITCODE)" }
    }

    # Step 1.5: 確保 bin\installers\ 有 installer 檔（供 chocolateyInstall.ps1 使用）
    if ($entry.source_dir) {
        $localInstallerDir = Join-Path $Root ($entry.source_dir -replace '/', '\')
        if (-not (Test-Path $localInstallerDir)) {
            if ($entry.nexus_path) {
                $zipName = ($entry.nexus_path -split '/')[-1]
                $nasZip  = Join-Path $NasZipBase $zipName
                $tmpZip  = Join-Path $env:TEMP $zipName
                Write-Host "  [COPY] installer $($entry.id)  $nasZip" -ForegroundColor Yellow
                try {
                    if (-not (Test-Path $nasZip)) {
                        Write-Warning "  [WARN] $($entry.id): zip not found on NAS: $nasZip"
                        Write-Warning "         Please run upload_tools_to_nexus.bat to publish the zip first."
                    } else {
                        Copy-Item -Path $nasZip -Destination $tmpZip -Force
                        New-Item -ItemType Directory -Path $localInstallerDir -Force | Out-Null
                        Expand-Archive -Path $tmpZip -DestinationPath $localInstallerDir -Force
                        Remove-Item $tmpZip -Force
                    }
                } catch {
                    Write-Warning "  [WARN] $($entry.id): failed to copy installer from NAS ($($_.Exception.Message))"
                    Write-Warning "         NAS path: $nasZip"
                    if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force }
                }
            } else {
                Write-Warning "  [WARN] $($entry.id): bin\installers missing and no nexus_path defined"
            }
        } else {
            Write-Host "  [SKIP] installer $($entry.id) (bin\installers already present)" -ForegroundColor DarkGray
        }
    }

}

Write-Host ""
Write-Host "Tools ready: $TestCase" -ForegroundColor Green
