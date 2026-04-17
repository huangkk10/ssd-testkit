<#
.SYNOPSIS
  1. Upload .nupkg files from bin\chocolatey\packages\ to Nexus choco-hosted repo.
     If a .nupkg is missing, it is built first via 'choco pack' from the nuspec source.
  2. Zip bin\installers\<tool>\ and copy to NAS ssd-testkit-source\windows\zip\.

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
    [string]$NexusUrl  = "https://10.252.170.171",
    [string]$Repo      = "choco-hosted-nas",
    [string]$NexusUser = "admin",
    [string]$NexusPass = "1.a"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

[Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root     = Split-Path $PSScriptRoot
$Registry = Join-Path $Root "lib\testtool\tools-registry.yaml"
$NasShare = "\\10.250.0.1\mdt"
$NasUser  = "mdt"
$NasPass  = "p@ssw0rd"

# 確保 NAS share 已掛載
if (-not (Test-Path $NasShare -ErrorAction SilentlyContinue)) {
    Write-Host "  [NAS] Connecting to $NasShare ..." -ForegroundColor DarkCyan
    $netResult = net use $NasShare /user:$NasUser $NasPass 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Warning "  [WARN] Failed to connect to NAS: $netResult" }
}

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
        # nuspec lives inside the version directory (e.g. packages\smicli\2026.2.13\smicli.nuspec)
        $nuspec = Get-ChildItem $pkgDir -Filter "*.nuspec" -ErrorAction SilentlyContinue |
                  Select-Object -First 1
        if ($nuspec) {
            Write-Host "  [PACK]   $id $version" -ForegroundColor DarkYellow
            $chocoExe = if (Test-Path "C:\ProgramData\chocolatey\bin\choco.exe") { "C:\ProgramData\chocolatey\bin\choco.exe" } else { "choco" }
            & $chocoExe pack $nuspec.FullName --outputdirectory $pkgDir --version $version
        } else {
            Write-Warning "[SKIP] ${id}: no .nupkg at $nupkg and no .nuspec in $pkgDir"
            continue
        }
    }

    if (-not (Test-Path $nupkg)) {
        Write-Warning "[SKIP] ${id}: .nupkg still missing after pack"
        continue
    }

    $sizeMB = [math]::Round((Get-Item $nupkg).Length / 1MB, 2)
    Write-Host "  [UPLOAD] $id $version  (${sizeMB} MB)" -ForegroundColor Cyan

    $output = & curl.exe -sk --ssl-no-revoke --noproxy "10.252.170.171" -u "${NexusUser}:${NexusPass}" `
        -F "nuget.asset=@$nupkg" `
        -w "`nHTTP_CODE:%{http_code}" `
        $uploadUrl 2>&1

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

# ── Installer zips → NAS ────────────────────────────────────────────────────
$NasZipBase = "\\10.250.0.1\mdt\Team\PQ1-3\tool\ssd-testkit-source\windows\zip"

Write-Host ""
Write-Host "== Installer zips -> NAS ==================================" -ForegroundColor White

$pyScript2 = @"
import sys, yaml, json
with open(sys.argv[1], encoding='utf-8') as f:
    registry = yaml.safe_load(f).get('tools', {})
result = []
for tid, reg in registry.items():
    sd = reg.get('source_dir', '')
    np = reg.get('nexus_path', '')
    if sd and np:
        result.append({'id': tid, 'source_dir': sd, 'nexus_path': np})
print(json.dumps(result))
"@

$zipEntries = python -c $pyScript2 $Registry | ConvertFrom-Json

if (-not (Test-Path $NasZipBase)) {
    Write-Warning "NAS not accessible: $NasZipBase"
    Write-Warning "Skipping installer zip upload."
} else {
    foreach ($entry in $zipEntries) {
        $zipName       = ($entry.nexus_path -split '/')[-1]
        $nasZipTarget  = Join-Path $NasZipBase $zipName
        $localSourceDir = Join-Path $Root ($entry.source_dir -replace '/', '\')
        $tmpZip        = Join-Path $env:TEMP $zipName

        if (Test-Path $nasZipTarget) {
            Write-Host "  [EXISTS] $($entry.id)  ($nasZipTarget)" -ForegroundColor DarkGray
            continue
        }

        if (-not (Test-Path $localSourceDir)) {
            Write-Warning "  [SKIP] $($entry.id): source not found: $localSourceDir"
            continue
        }

        Write-Host "  [ZIP]    $($entry.id)  $localSourceDir" -ForegroundColor DarkYellow
        Compress-Archive -Path "$localSourceDir\*" -DestinationPath $tmpZip -Force

        $sizeMB = [math]::Round((Get-Item $tmpZip).Length / 1MB, 2)
        Write-Host "  [COPY]   $($entry.id)  → $nasZipTarget  (${sizeMB} MB)" -ForegroundColor Cyan
        Copy-Item -Path $tmpZip -Destination $nasZipTarget -Force
        Remove-Item $tmpZip -Force
        Write-Host "  [OK]     $($entry.id)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Upload complete." -ForegroundColor Green
