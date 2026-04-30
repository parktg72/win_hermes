@echo off
chcp 65001 >nul
setlocal

REM 외부망(PyPI/GitHub 접근 가능) PC에서 더블클릭하여 폐쇄망 배포에 필요한
REM 두 가지를 한 번에 받는 스크립트:
REM   1) vendor\uv.exe         (astral-sh/uv 공식 릴리스, SHA256 검증)
REM   2) vendor\wheels\*.whl   (win_amd64 / cp312 휠, 핵심 4종 검증)

cd /d "%~dp0"

echo.
echo === win_hermes 오프라인 준비 다운로더 ===
echo.

echo [1/4] Python 3.12 확인 중...
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [오류] Python 3.12를 찾을 수 없습니다.
    echo python.org 에서 3.12.x 버전을 설치한 후 다시 실행하세요.
    echo.
    pause
    exit /b 1
)
echo OK
echo.

echo [2/4] uv.exe 다운로드 ^(SHA256 검증 포함^)...
py -3.12 scripts\download_uv.py
set UV_RC=%ERRORLEVEL%
echo.

if %UV_RC% NEQ 0 (
    echo [실패] uv.exe 다운로드 실패 ^(종료 코드 %UV_RC%^).
    echo 위 메시지를 확인 후 다시 시도하세요. UV_VERSION 환경변수로 버전 변경 가능.
    echo.
    pause
    exit /b %UV_RC%
)

echo [3/4] 휠 다운로드 시작 ^(몇 분 걸릴 수 있습니다^)...
py -3.12 scripts\download_wheels.py
set DL_RC=%ERRORLEVEL%
echo.

if %DL_RC% NEQ 0 (
    echo [실패] 휠 다운로드 중 문제가 발생했습니다 ^(종료 코드 %DL_RC%^).
    echo 위 메시지를 확인 후 다시 시도하세요.
    echo.
    pause
    exit /b %DL_RC%
)

echo [4/4] 완료
echo.
echo vendor\ 폴더 전체 ^(uv.exe + wheels\^)를 사내망 PC로 복사한 뒤
echo install.bat을 실행하세요.
echo.
pause
exit /b 0
