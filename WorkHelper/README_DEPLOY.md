# 6PM Assistant 빌드 & 배포 가이드

## 구조 개요

```
dist/
  6PM Assistant.exe   ← 메인 앱 (배포 대상)
  updater.exe         ← 자동 업데이트용 파일 교체기 (함께 배포)
```

사용자는 두 파일을 **같은 폴더**에 두고 `6PM Assistant.exe`를 실행합니다.  
Python, PyQt6 등 별도 설치 불필요합니다.

---

## 방법 A — 로컬 빌드 후 직접 배포 (권장)

### 사전 준비 (최초 1회)
```powershell
# gh CLI 설치 (GitHub Release 자동 생성에 필요)
winget install --id GitHub.cli

# gh 로그인
gh auth login
```

### 배포 명령

```powershell
# WorkHelper 폴더에서 실행
cd C:\...\support_cdx\WorkHelper

# 패치 버전 자동 올리기 (1.0.0 → 1.0.1)
.\build_release.ps1

# 버전·릴리즈 노트 직접 지정
.\build_release.ps1 -Version 1.2.0 -ReleaseNote "UI 개선 및 버그 수정"

# pip 재설치 없이 빌드만 (배포 없음)
.\build_release.ps1 -SkipInstall -SkipRelease
```

### 스크립트가 자동으로 하는 일

| 단계 | 내용 |
|------|------|
| 1 | `version.txt` 버전 번호 업데이트 |
| 2 | `pip install -r requirements.txt` |
| 3 | PyInstaller로 `6PM Assistant.exe` + `updater.exe` 빌드 |
| 4 | `git commit` → `git tag vX.Y.Z` → `git push` |
| 5 | `gh release create`로 GitHub Release 생성 및 exe 업로드 |

---

## 방법 B — GitHub Actions 자동 빌드 (클라우드)

코드 변경 후 버전 태그만 푸시하면 GitHub이 빌드 & Release를 자동으로 생성합니다.

```powershell
# version.txt 수정 후 커밋
echo "1.2.0" > version.txt
git add WorkHelper/version.txt
git commit -m "chore: release v1.2.0"

# 태그 푸시 → GitHub Actions 자동 실행
git tag v1.2.0
git push origin main
git push origin v1.2.0
```

워크플로우 파일: `.github/workflows/release.yml`

> ⚠️ GitHub Actions Windows 빌드는 10~20분 소요될 수 있습니다.  
> 속도가 중요하면 방법 A(로컬 빌드)를 사용하세요.

---

## 업데이트 동작 방식

```
앱 시작 또는 "업데이트 확인" 버튼
    ↓
GitHub API로 최신 Release 태그 확인
    ↓ (새 버전 있으면)
exe 다운로드 → updater.exe 실행
    ↓
updater.exe가 기존 exe 교체 → 앱 재시작
```

- 확인 위치: **설정 탭 → 업데이트 확인** 버튼
- 자동 확인: **설정 탭 → 일반 → 업데이트 확인** 체크박스
- 자동 교체: **설정 탭 → 일반 → 자동 업데이트** 체크박스 (exe 실행 중일 때만 동작)

---

## 개발 환경에서 직접 실행

```powershell
python -m pip install -r requirements.txt
python main.py
```
