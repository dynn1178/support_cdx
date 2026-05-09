<#
.SYNOPSIS
    6PM Assistant 빌드 & GitHub Release 배포 스크립트

.PARAMETER Version
    배포할 버전 번호 (예: 1.2.0). 생략하면 현재 버전에서 패치 번호를 자동으로 +1합니다.

.PARAMETER ReleaseNote
    GitHub Release에 표시할 릴리즈 노트. 생략하면 버전 번호만 표시됩니다.

.PARAMETER SkipInstall
    pip install 단계를 건너뜁니다. 이미 패키지가 설치되어 있을 때 사용합니다.

.PARAMETER SkipRelease
    빌드만 수행하고 git 커밋/태그/GitHub Release 생성을 건너뜁니다.

.EXAMPLE
    .\build_release.ps1
    .\build_release.ps1 -Version 1.2.0 -ReleaseNote "UI 개선 및 버그 수정"
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

$ProjectRoot     = Split-Path -Parent $MyInvocation.MyCommand.Path   # WorkHelper/
$GitRoot         = Split-Path -Parent $ProjectRoot                    # support_cdx/
$VersionFile     = Join-Path $ProjectRoot "version.txt"
$SpecPath        = Join-Path $ProjectRoot "build\WorkHelper.spec"
$DistDir         = Join-Path $ProjectRoot "dist"
$UpdaterDistDir  = Join-Path $ProjectRoot "build\_updater_dist"       # spec이 참조하는 경로
$ExePath         = Join-Path $DistDir "6PM Assistant.exe"

Set-Location $ProjectRoot

# ─────────────────────────────────────────────────────────────────────
# 1. 버전 결정 및 version.txt 업데이트
# ─────────────────────────────────────────────────────────────────────
$currentVersion = (Get-Content $VersionFile -Raw -Encoding utf8).Trim()

if (-not $Version) {
    $parts = $currentVersion -split '\.'
    $parts[-1] = [string]([int]$parts[-1] + 1)
    $Version = $parts -join '.'
}

Write-Host ""
Write-Host "==========================================="
Write-Host " 6PM Assistant 빌드 & 배포"
Write-Host " $currentVersion  →  $Version"
Write-Host "==========================================="
Write-Host ""

Set-Content $VersionFile $Version -NoNewline -Encoding utf8
Write-Host "[1/5] version.txt 업데이트: $Version"

# ─────────────────────────────────────────────────────────────────────
# 2. pip install
# ─────────────────────────────────────────────────────────────────────
if (-not $SkipInstall) {
    Write-Host "[2/5] 패키지 설치 중..."
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt --quiet
    Write-Host "[2/5] 패키지 설치 완료"
} else {
    Write-Host "[2/5] pip install 건너뜀 (-SkipInstall)"
}

# ─────────────────────────────────────────────────────────────────────
# 3. 빌드 (updater 먼저 → 메인 exe 번들에 포함)
# ─────────────────────────────────────────────────────────────────────
Write-Host "[3/5] updater.exe 빌드 중..."
New-Item -ItemType Directory -Force -Path $UpdaterDistDir | Out-Null
python -m PyInstaller --clean --noconfirm --onefile --name updater `
    --distpath $UpdaterDistDir `
    --workpath (Join-Path $ProjectRoot "build\_updater_build") `
    updater.py

$UpdaterPath = Join-Path $UpdaterDistDir "updater.exe"
if (-not (Test-Path $UpdaterPath)) { throw "updater.exe 빌드 실패" }
Write-Host "[3/5] updater.exe 완료 → 메인 exe에 번들로 포함됩니다"

Write-Host "[3/5] 메인 앱 빌드 중 (시간이 걸릴 수 있습니다)..."
python -m PyInstaller --clean --noconfirm $SpecPath

if (-not (Test-Path $ExePath)) { throw "빌드 실패: $ExePath 를 찾을 수 없습니다" }

$sizeMB = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
Write-Host "[3/5] 빌드 완료 → $ExePath ($sizeMB MB)"

if ($SkipRelease) {
    Write-Host ""
    Write-Host "빌드 완료 (-SkipRelease 지정으로 배포 단계를 건너뜁니다)"
    Write-Host "배포 파일: $ExePath"
    exit 0
}

# ─────────────────────────────────────────────────────────────────────
# 4. git 커밋 + 태그 + 푸시
# ─────────────────────────────────────────────────────────────────────
$tag = "v$Version"
Write-Host "[4/5] git 커밋 & 태그 ($tag) ..."
Set-Location $GitRoot

git add "WorkHelper/version.txt"
git commit -m "chore: release $tag"
git tag $tag
git push origin main
git push origin $tag

Write-Host "[4/5] git 푸시 완료 (태그: $tag)"

# ─────────────────────────────────────────────────────────────────────
# 5. GitHub Release 생성 — exe 1개만 업로드
# ─────────────────────────────────────────────────────────────────────
Write-Host "[5/5] GitHub Release 생성 중..."

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "[알림] gh CLI가 없어 GitHub Release를 수동으로 생성해야 합니다."
    Write-Host "  1. https://github.com/dynn1178/support_cdx/releases/new 접속"
    Write-Host "  2. Tag: $tag 입력"
    Write-Host "  3. 파일 업로드: $ExePath"
    Write-Host ""
    Write-Host "  gh CLI 설치: winget install --id GitHub.cli"
} else {
    $notes = if ($ReleaseNote) { $ReleaseNote } else { "## v$Version`n`n변경 사항을 여기에 작성하세요." }
    gh release create $tag `
        "$ExePath" `
        --repo "dynn1178/support_cdx" `
        --title "v$Version" `
        --notes $notes

    Write-Host "[5/5] GitHub Release 생성 완료"
    Write-Host "       https://github.com/dynn1178/support_cdx/releases/tag/$tag"
}

Write-Host ""
Write-Host "==========================================="
Write-Host " 배포 완료: v$Version"
Write-Host " 사용자는 6PM Assistant.exe 1개만 받으면 됩니다."
Write-Host "==========================================="
