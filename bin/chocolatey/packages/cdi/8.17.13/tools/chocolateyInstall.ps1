$cdiVersion = "8.17.13"
$installDir = "C:\tools\CrystalDiskInfo"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if (-not $toolkitRoot) {
    throw "SSD_TESTKIT_ROOT is not set. Run via install_packages.ps1 or set it manually."
}

$sourceDir = Join-Path $toolkitRoot "bin\installers\CrystalDiskInfo\$cdiVersion"
if (-not (Test-Path $sourceDir)) {
    throw "Source not found: $sourceDir"
}

Write-Host "Installing CrystalDiskInfo $cdiVersion to $installDir..."
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

[Environment]::SetEnvironmentVariable('CDI_PATH', "$installDir\DiskInfo64.exe", 'Machine')
Write-Host "CrystalDiskInfo $cdiVersion installed to $installDir"
Write-Host "CDI_PATH = $installDir\DiskInfo64.exe"
