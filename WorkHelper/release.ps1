<#
.SYNOPSIS
    6PM Assistant 릴리즈 마법사.

    릴리즈 버전과 업데이트 내용을 물어본 뒤 빌드 → git 커밋/태그/푸시 →
    GitHub Release 생성까지 한 번에 진행한다. release.bat 이 이 스크립트를 실행한다.

    실제 빌드/배포 작업은 build_release.ps1 이 담당하고, 이 스크립트는 입력과 확인만 맡는다.
#>
param(
    [string]$Version = "",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildScript = Join-Path $ProjectRoot "build_release.ps1"
$VersionFile = Join-Path $ProjectRoot "version.txt"
$NotesFile   = Join-Path $env:TEMP "6pm_release_notes.txt"
$RepoSlug    = "dynn1178/support_cdx"

Set-Location $ProjectRoot

function Write-Title($text) {
    Write-Host ""
    Write-Host "===========================================" -ForegroundColor DarkGray
    Write-Host " $text" -ForegroundColor White
    Write-Host "===========================================" -ForegroundColor DarkGray
}

function Fail($message) {
    Write-Host ""
    Write-Host "[중단] $message" -ForegroundColor Red
    exit 1
}

Write-Title "6PM Assistant 릴리즈"

# --- 1. 사전 점검 -----------------------------------------------------------
foreach ($tool in @("git", "python")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Fail "$tool 을(를) 찾을 수 없습니다. 설치 후 다시 실행해 주세요."
    }
}
if (-not (Test-Path $BuildScript)) { Fail "build_release.ps1 을 찾을 수 없습니다." }
if (-not (Test-Path $VersionFile)) { Fail "version.txt 를 찾을 수 없습니다." }

$hasGh = [bool](Get-Command gh -ErrorAction SilentlyContinue)
if (-not $hasGh) {
    Write-Host "[주의] gh CLI 가 없어 GitHub Release 는 직접 만들어야 합니다." -ForegroundColor Yellow
    Write-Host "       설치: winget install --id GitHub.cli" -ForegroundColor Yellow
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne "main") {
    Write-Host "[주의] 현재 브랜치가 main 이 아닙니다: $branch" -ForegroundColor Yellow
}

# --- 2. 버전 ---------------------------------------------------------------
$current = (Get-Content $VersionFile -Raw -Encoding utf8).Trim()
$parts = $current -split '\.'
$suggest = if ($parts.Count -eq 3) {
    "{0}.{1}.{2}" -f $parts[0], $parts[1], ([int]$parts[2] + 1)
} else {
    $current
}

Write-Host ""
Write-Host " 현재 버전: $current" -ForegroundColor Gray
if (-not $Version) {
    while ($true) {
        $typed = (Read-Host " 릴리즈 버전 (Enter = $suggest)").Trim()
        if (-not $typed) { $Version = $suggest; break }
        if ($typed -match '^\d+\.\d+\.\d+$') { $Version = $typed; break }
        Write-Host "  버전은 1.2.3 형식으로 입력해 주세요." -ForegroundColor Yellow
    }
}
$tag = "v$Version"

# --- 3. 업데이트 내용 -------------------------------------------------------
Write-Host ""
Write-Host " 업데이트 내용을 한 줄씩 입력하세요. (빈 줄 = 입력 끝)" -ForegroundColor Gray
Write-Host " 마크다운을 그대로 쓸 수 있습니다. 예) - 메모 자동 숨김 기능 추가" -ForegroundColor DarkGray
$lines = New-Object System.Collections.Generic.List[string]
while ($true) {
    $line = Read-Host " "
    if (-not $line) { break }
    $lines.Add($line)
}
if ($lines.Count -eq 0) {
    $lines.Add("- 개선 및 버그 수정")
    Write-Host "  (입력이 없어 기본 문구를 사용합니다: - 개선 및 버그 수정)" -ForegroundColor DarkGray
}
$notes = "## $tag" + [Environment]::NewLine + [Environment]::NewLine + ($lines -join [Environment]::NewLine)
[System.IO.File]::WriteAllText($NotesFile, $notes, (New-Object System.Text.UTF8Encoding($false)))

# --- 4. 배포 범위 -----------------------------------------------------------
Write-Host ""
Write-Host " 1) 전체 릴리즈 - 빌드 + git 커밋/태그/푸시 + GitHub Release" -ForegroundColor Gray
Write-Host " 2) 빌드만     - dist 폴더에 exe/zip 만 만들고 끝" -ForegroundColor Gray
$mode = (Read-Host " 선택 (Enter = 1)").Trim()
if (-not $mode) { $mode = "1" }
$buildOnly = ($mode -eq "2")

# --- 5. 확인 ---------------------------------------------------------------
if (-not $buildOnly) {
    $changed = @(git status --short)
    Write-Host ""
    if ($changed.Count -gt 0) {
        Write-Host " 아래 변경 사항이 릴리즈 커밋에 함께 올라갑니다 ($($changed.Count)개):" -ForegroundColor Gray
        $changed | Select-Object -First 15 | ForEach-Object { Write-Host "   $_" -ForegroundColor DarkGray }
        if ($changed.Count -gt 15) { Write-Host "   ... 외 $($changed.Count - 15)개" -ForegroundColor DarkGray }
    } else {
        Write-Host " 변경된 파일이 없습니다 (버전 파일만 올라갑니다)." -ForegroundColor DarkGray
    }
}

Write-Title "확인"
Write-Host " 버전   : $current  ->  $Version"
Write-Host " 태그   : $tag"
Write-Host " 작업   : $(if ($buildOnly) { '빌드만 (배포 안 함)' } else { '빌드 + git push + GitHub Release' })"
Write-Host " 업데이트 내용:"
foreach ($line in $lines) { Write-Host "   $line" -ForegroundColor DarkGray }
Write-Host ""

$answer = (Read-Host " 진행할까요? (Y/N, Enter = Y)").Trim()
if ($answer -and $answer -notmatch '^(y|yes)$') {
    Write-Host ""
    Write-Host " 취소했습니다. 버전 파일은 그대로입니다." -ForegroundColor Yellow
    exit 0
}

# --- 6. 실행 ---------------------------------------------------------------
$buildArgs = @{
    Version         = $Version
    ReleaseNoteFile = $NotesFile
}
if ($buildOnly)   { $buildArgs["SkipRelease"] = $true }
if ($SkipInstall) { $buildArgs["SkipInstall"] = $true }

$started = Get-Date
try {
    & $BuildScript @buildArgs
} catch {
    Fail "빌드/배포 중 오류가 발생했습니다.`n$($_.Exception.Message)"
}

Remove-Item $NotesFile -ErrorAction SilentlyContinue
$elapsed = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)

Write-Title "완료 ($elapsed 분)"
if ($buildOnly) {
    Write-Host " dist 폴더의 6PM.Assistant.zip 을 확인하세요." -ForegroundColor Green
} else {
    Write-Host " 릴리즈 $tag 배포 완료" -ForegroundColor Green
    if ($hasGh) {
        Write-Host " https://github.com/$RepoSlug/releases/tag/$tag" -ForegroundColor Green
    }
}
Write-Host ""
