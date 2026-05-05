# chocolateyUninstall.ps1  chrome 147.0.7727.138

$toolVersion = "147.0.7727.138"
$installDir  = "C:\Program Files\Google\Chrome"

Write-Host "Uninstalling Google Chrome $toolVersion ..."

# Locate Chrome uninstaller via registry
$uninstallKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
$chromeKey = Get-ChildItem $uninstallKey | Where-Object {
    (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DisplayName -like "*Google Chrome*"
} | Select-Object -First 1

if ($chromeKey) {
    $uninstallStr = (Get-ItemProperty $chromeKey.PSPath).UninstallString
    Write-Host "Found uninstall entry: $uninstallStr"
    $proc = Start-Process -FilePath "msiexec.exe" `
        -ArgumentList "/x `"$($chromeKey.PSChildName)`" /quiet /norestart" `
        -Wait -PassThru
    if ($proc.ExitCode -notin @(0, 3010)) {
        Write-Warning "Chrome uninstaller returned exit code: $($proc.ExitCode)"
    }
} else {
    Write-Warning "Chrome registry key not found - removing directory manually."
    if (Test-Path $installDir) {
        Remove-Item $installDir -Recurse -Force
        Write-Host "Removed $installDir"
    }
}

[Environment]::SetEnvironmentVariable('CHROME_PATH', $null, 'Machine')
Write-Host "Google Chrome uninstalled. CHROME_PATH cleared."
