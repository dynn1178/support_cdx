# WorkHelper 배포 방법

`main.py`를 그대로 다른 PC에서 실행하면 그 PC의 Python에 `PyQt6` 같은 모듈이 설치되어 있어야 합니다. 처음 실행하는 PC에서도 별도 설치 없이 실행되게 하려면, 개발 PC에서 먼저 실행 파일로 패키징해서 배포하세요.

## 빌드

PowerShell에서 `WorkHelper` 폴더로 이동한 뒤 실행합니다.

```powershell
.\build_release.ps1
```

이미 필요한 패키지가 설치되어 있고 재설치 없이 빌드만 하고 싶으면:

```powershell
.\build_release.ps1 -SkipInstall
```

## 배포

빌드가 끝나면 아래 파일이 생성됩니다.

```text
dist\6PM Assistant.exe
```

이 `.exe` 파일을 사용자 PC에 전달하면 됩니다. 사용자 PC에는 Python, PyQt6, pip 패키지를 따로 설치하지 않아도 됩니다.

## 개발 PC에서 직접 실행

개발 중 `main.py`를 직접 실행하려면 한 번은 의존성을 설치해야 합니다.

```powershell
python -m pip install -r requirements.txt
python main.py
```

