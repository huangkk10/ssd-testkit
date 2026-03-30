<#
.SYNOPSIS
  Upload .nupkg files from bin\chocolatey\packages\ to Nexus choco-hosted repo.
  If a .nupkg is missing, it is built first via 'choco pack' from the nuspec source.

.PARAMETER NexusUrl
  Nexus base URL, default https://nexus.internal

.PARAMETER Repo
  Nexus repository name, default choco-hosted

.PARAMETER NexusUser / NexusPass
  Nexus credentials

.EXAMPLE
  .\tool-manager\upload_tools_to_nexus.ps1
  .\tool-manager\upload_tools_to_nexus.ps1 -NexusUser uploader -NexusPass "Uploader@2026"

.NOTES
  nupkg source : $Root\bin\chocolatey\packages\<id>\<version>\<id>.<version>.nupkg
  nuspec source: $Root\bin\chocolatey\packages\<id>\<id>.nuspec
  Upload target: POST $NexusUrl/service/rest/v1/components?repository=choco-hosted
#>
param(
    [string]$NexusUrl  = "https://nexus.internal",
    [string]$Repo      = "choco-hosted",
    [string]$NexusUser = "admin",
    [string]$NexusPass = "1.a"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

[Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root     = Split-Path $PSScriptRoot
$Registry = Join-Path $Root "lib\testtool\tools-registry.yaml"

if (-not (Test-Path $Registry)) { Write-Error "tools-registry.yaml not found: $Registry"; exit 1 }

$pyScript = @"
import sys, yaml, json
with open(sys.argv[1], encoding='utf-8') as f:
    registry = yaml.safe_load(f).get('tools', {})
result = []
for tid, reg in registry.items():
    ver = reg.get('version', '')
    if ver:
        result.append({'id': tid, 'version': str(ver)})
print(json.dumps(result))
"@

$entries = python -c $pyScript $Registry | ConvertFrom-Json
$uploadUrl = "$NexusUrl/service/rest/v1/components?repository=$Repo"

foreach ($entry in $entries) {
    $id      = $entry.id
    $version = [string]$entry.version
    $pkgDir  = Join-Path $Root "bin\chocolatey\packages\$id\$version"
    $nupkg   = Join-Path $pkgDir "$id.$version.nupkg"

    # Build .nupkg via choco pack if not present
    if (-not (Test-Path $nupkg)) {
        $nuspecDir = Join-Path $Root "bin\chocolatey\packages\$id"
        $nuspec    = Get-ChildItem $nuspecDir -Filter "*.nuspec" -ErrorAction SilentlyContinue |
                     Select-Object -First 1
        if ($nuspec) {
            Write-Host "  [PACK]   $id $version" -ForegroundColor DarkYellow
            New-Item -ItemType Directory -Force -Path $pkgDir | Out-Null
            choco pack $nuspec.FullName --outputdirectory $pkgDir --version $version
        } else {
            Write-Warning "[SKIP] $id: no .nupkg at $nupkg and no .nuspec in $nuspecDir"
            continue
        }
    }

    if (-not (Test-Path $nupkg)) {
        Write-Warning "[SKIP] $id: .nupkg still missing after pack"
        continue
    }

    $sizeMB = [math]::Round((Get-Item $nupkg).Length / 1MB, 2)
    Write-Host "  [UPLOAD] $id $version  (${sizeMB} MB)" -ForegroundColor Cyan

    $output = & curl.exe -sk -u "${NexusUser}:${NexusPass}" `
        -X POST $uploadUrl `
        -F "nuget.asset=@$nupkg" `
        -w "`nHTTP_CODE:%{http_code}" 2>&1

    $httpCode = ($output | Select-String "HTTP_CODE:(\d+)").Matches[0].Groups[1].Value

    switch ($httpCode) {
        { $_ -in @('200','201','204') } {
            Write-Host "  [OK]     $id  HTTP $httpCode" -ForegroundColor Green
        }
        '400' {
            if ($output -match 'already exists') {
                Write-Host "  [EXISTS] $id (already in $Repo, skipped)" -ForegroundColor DarkYellow
            } else {
                Write-Warning "[FAIL] $id  HTTP $httpCode"
                Write-Host ($output -join "`n")
            }
        }
        default {
            Write-Warning "[FAIL] $id  HTTP $httpCode"
            Write-Host ($output -join "`n")
        }
    }
}

Write-Host ""
Write-Host "Upload complete." -ForegroundColor Green
