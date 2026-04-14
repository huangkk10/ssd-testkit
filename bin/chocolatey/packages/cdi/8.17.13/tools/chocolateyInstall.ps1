# chocolateyInstall.ps1  cdi 8.17.13

$cdiVersion  = "8.17.13"
$installDir  = "C:\tools\CrystalDiskInfo"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\CrystalDiskInfo\$cdiVersion"
    if (-not (Test-Path $sourceDir)) {
        throw "Source not found: $sourceDir"
    }
} else {
    $nexusBase = "https://nexus.internal/repository/raw-windows-tools"
    $zip       = "$env:TEMP\CrystalDiskInfo-$cdiVersion.zip"
    $sourceDir = "$env:TEMP\CrystalDiskInfo-$cdiVersion"
    Write-Host "Downloading CrystalDiskInfo from Nexus ..."
    iwr "$nexusBase/CrystalDiskInfo/$cdiVersion/CrystalDiskInfo-$cdiVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $sourceDir) { Remove-Item $sourceDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $sourceDir -Force
}

Write-Host "Installing CrystalDiskInfo $cdiVersion to $installDir..."
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

[Environment]::SetEnvironmentVariable('CDI_PATH', "$installDir\DiskInfo64.exe", 'Machine')
Write-Host "CrystalDiskInfo $cdiVersion installed to $installDir"
Write-Host "CDI_PATH = $installDir\DiskInfo64.exe"
