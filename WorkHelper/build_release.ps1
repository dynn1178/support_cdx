<#
.SYNOPSIS
    Build and release 6PM Assistant.

.PARAMETER Version
    Version to release (e.g. 1.2.0). Auto-increments patch if omitted.

.PARAMETER ReleaseNote
    Release notes for GitHub Release.

.PARAMETER SkipInstall
    Skip pip install step.

.PARAMETER SkipRelease
    Build only - skip git commit/tag/push and GitHub Release.

.EXAMPLE
    .\build_release.ps1
    .\build_release.ps1 -Version 1.2.0 -ReleaseNote "UI improvements"
    .\build_release.ps1 -SkipInstall -SkipRelease
#>
param(
    [string]$Version     = "",
    [string]$ReleaseNote = "",
    [switch]$SkipInstall,
    [switch]$SkipRelease
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot    = Split-Path -Parent $MyInvocation.MyCommand.Path
$GitRoot        = Split-Path -Parent $ProjectRoot
$VersionFile    = Join-Path $ProjectRoot "version.txt"
$SpecPath       = Join-Path $ProjectRoot "build\WorkHelper.spec"
$DistDir        = Join-Path $ProjectRoot "dist"
$UpdaterDistDir = Join-Path $ProjectRoot "build\_updater_dist"
$ExePath        = Join-Path $DistDir "6PM Assistant.exe"
$DistUpdaterPath = Join-Path $DistDir "updater.exe"

Set-Location $ProjectRoot

# --- 1. Version ---
$currentVersion = (Get-Content $VersionFile -Raw -Encoding utf8).Trim()

if (-not $Version) {
    $parts = $currentVersion -split '\.'
    $parts[-1] = [string]([int]$parts[-1] + 1)
    $Version = $parts -join '.'
}

$ZipPath = Join-Path $DistDir "6PM.Assistant.zip"

Write-Host ""
Write-Host "==========================================="
Write-Host " 6PM Assistant Build"
Write-Host " $currentVersion  ->  $Version"
Write-Host "==========================================="
Write-Host ""

[System.IO.File]::WriteAllText($VersionFile, $Version, [System.Text.UTF8Encoding]::new($false))
Write-Host "[1/5] version.txt updated: $Version"

# --- 2. pip install ---
if (-not $SkipInstall) {
    Write-Host "[2/5] Installing packages..."
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt --quiet
    Write-Host "[2/5] Packages installed"
} else {
    Write-Host "[2/5] Skipping pip install (-SkipInstall)"
}

# --- 3. Build ---
Write-Host "[3/5] Building updater.exe..."
New-Item -ItemType Directory -Force -Path $UpdaterDistDir | Out-Null
python -m PyInstaller --clean --noconfirm --onefile --name updater `
    --windowed `
    --distpath $UpdaterDistDir `
    --workpath (Join-Path $ProjectRoot "build\_updater_build") `
    updater.py

$UpdaterPath = Join-Path $UpdaterDistDir "updater.exe"
if (-not (Test-Path $UpdaterPath)) { throw "updater.exe build failed" }
Write-Host "[3/5] updater.exe built"

Write-Host "[3/5] Building main app (this may take a few minutes)..."
python -m PyInstaller --clean --noconfirm $SpecPath

if (-not (Test-Path $ExePath)) { throw "Build failed: $ExePath not found" }
Copy-Item -Force $UpdaterPath $DistUpdaterPath
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path $ExePath, $DistUpdaterPath -DestinationPath $ZipPath

$sizeMB = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
$zipSizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host "[3/5] Build complete -> $ExePath ($sizeMB MB)"
Write-Host "[3/5] Updater copied -> $DistUpdaterPath"
Write-Host "[3/5] Zip package -> $ZipPath ($zipSizeMB MB)"

if ($SkipRelease) {
    Write-Host ""
    Write-Host "Build complete (-SkipRelease: skipping git and GitHub steps)"
    Write-Host "Output: $ZipPath"
    exit 0
}

# --- 4. git commit + tag + push ---
$tag = "v$Version"
Write-Host "[4/5] git commit, tag ($tag), push..."
Set-Location $GitRoot

git add "WorkHelper/" ".github/workflows/release.yml"
git commit -m "chore: release $tag"
git tag $tag
git push origin main
git push origin $tag

Write-Host "[4/5] git push done (tag: $tag)"

# --- 5. GitHub Release ---
Write-Host "[5/5] Creating GitHub Release..."

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "[INFO] gh CLI not found. Create the release manually:"
    Write-Host "  1. https://github.com/dynn1178/support_cdx/releases/new"
    Write-Host "  2. Tag: $tag"
    Write-Host "  3. Upload: $ZipPath"
    Write-Host ""
    Write-Host "  Install gh CLI: winget install --id GitHub.cli"
} else {
    $notes = if ($ReleaseNote) { $ReleaseNote } else { "## $tag`n`nRelease notes here." }
    gh release create $tag `
        "$ZipPath" `
        --repo "dynn1178/support_cdx" `
        --title $tag `
        --notes $notes

    Write-Host "[5/5] GitHub Release created"
    Write-Host "      https://github.com/dynn1178/support_cdx/releases/tag/$tag"
}

Write-Host ""
Write-Host "==========================================="
Write-Host " Done: $Version"
Write-Host " Users only need the zip package"
Write-Host "==========================================="
