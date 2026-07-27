# Bootstraps Python 3.11 if it's not already on PATH.
$ErrorActionPreference = "Stop"

$pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$installerPath = Join-Path $env:TEMP "python-3.11.9-installer.exe"

Write-Host "Downloading Python 3.11.9 installer..."
Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath

Write-Host "Running silent install (adds to PATH for current user)..."
$proc = Start-Process -FilePath $installerPath -ArgumentList @(
    "/quiet",
    "InstallAllUsers=0",
    "PrependPath=1",
    "Include_test=0"
) -Wait -PassThru

Remove-Item $installerPath -ErrorAction SilentlyContinue

if ($proc.ExitCode -ne 0) {
    Write-Host "Python installer exited with code $($proc.ExitCode)"
    exit 1
}

Write-Host "Python 3.11.9 installed."
exit 0
