param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SpecPath = Join-Path $ProjectRoot "build\WorkHelper.spec"
$ExePath = Join-Path $ProjectRoot "dist\6PM Assistant.exe"
$UpdaterPath = Join-Path $ProjectRoot "dist\updater.exe"

Set-Location $ProjectRoot

if (-not $SkipInstall) {
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
}

python -m PyInstaller --clean --noconfirm $SpecPath
python -m PyInstaller --clean --noconfirm --onefile --name updater updater.py

if (-not (Test-Path $ExePath)) {
    throw "Build finished, but the executable was not found: $ExePath"
}
if (-not (Test-Path $UpdaterPath)) {
    throw "Build finished, but the updater was not found: $UpdaterPath"
}

Write-Host ""
Write-Host "Build complete:"
Write-Host $ExePath
Write-Host $UpdaterPath
Write-Host ""
Write-Host "Distribute the executable and updater in the dist folder. Target PCs do not need Python or pip packages installed."
