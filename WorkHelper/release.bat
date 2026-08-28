@echo off
rem ===========================================================
rem  6PM Assistant release launcher
rem  Double-click to run the release wizard:
rem    version -> release notes -> build -> git push -> GitHub Release
rem  All prompts and messages live in release.ps1 (Korean, UTF-8).
rem  Pass-through args are forwarded, e.g. release.bat -SkipInstall
rem ===========================================================
chcp 65001 >nul
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release.ps1" %*
set "RESULT=%ERRORLEVEL%"

echo.
pause
exit /b %RESULT%
