@echo off
chcp 65001 >nul
setlocal

REM 외부망(PyPI 접근 가능) PC에서 더블클릭으로 휠을 받아
REM vendor\wheels\ 폴더를 채우는 스크립트.
REM 다운로드 후 핵심 패키지 4종을 자동 검증합니다.

cd /d "%~dp0"

echo.
echo === win_hermes 오프라인 휠 다운로더 ===
echo.

echo [1/3] Python 3.12 확인 중...
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

echo [2/3] 휠 다운로드 시작 ^(몇 분 걸릴 수 있습니다^)...
py -3.12 scripts\download_wheels.py
set DL_RC=%ERRORLEVEL%
echo.

if %DL_RC% NEQ 0 (
    echo [실패] 다운로드 중 문제가 발생했습니다 ^(종료 코드 %DL_RC%^).
    echo 위 메시지를 확인 후 다시 시도하세요.
    echo.
    pause
    exit /b %DL_RC%
)

echo [3/3] 완료
echo.
echo vendor 폴더 전체를 사내망 PC로 복사한 뒤 install.bat을 실행하세요.
echo.
pause
exit /b 0
