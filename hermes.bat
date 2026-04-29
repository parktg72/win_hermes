@echo off
chcp 65001 >nul
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [오류] 설치가 완료되지 않았습니다. install.bat을 먼저 실행하세요.
    pause
    exit /b 1
)
"%~dp0venv\Scripts\python.exe" -m hermes_cli.main %*
exit /b %ERRORLEVEL%
