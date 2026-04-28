# chocolateyInstall.ps1  diskercise 1.0.0.1

$toolVersion = "1.0.0.1"
$installDir  = "C:\tools\Diskercise"
$toolkitRoot = $env:SSD_TESTKIT_ROOT

if ($toolkitRoot) {
    $sourceDir = Join-Path $toolkitRoot "bin\installers\Diskercise\$toolVersion"
    if (-not (Test-Path $sourceDir)) {
        throw "Source not found: $sourceDir"
    }
} else {
    $nexusBase = "https://nexus.internal/repository/raw-windows-tools"
    $zip       = "$env:TEMP\Diskercise-$toolVersion.zip"
    $sourceDir = "$env:TEMP\Diskercise-$toolVersion"
    Write-Host "Downloading Diskercise from Nexus ..."
    iwr "$nexusBase/Diskercise/$toolVersion/Diskercise-$toolVersion.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $sourceDir) { Remove-Item $sourceDir -Recurse -Force }
    Expand-Archive $zip -DestinationPath $sourceDir -Force
}

Write-Host "Installing Diskercise $toolVersion to $installDir ..."
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

[Environment]::SetEnvironmentVariable('DISKERCISE_PATH', $installDir, 'Machine')
Write-Host "Diskercise $toolVersion installed to $installDir"
Write-Host "DISKERCISE_PATH = $installDir"
