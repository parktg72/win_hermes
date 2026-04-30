@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
set "WHEEL_DIR=%~dp0vendor\wheels"

echo === Hermes Windows Installer ===
echo.

cd /d "!SCRIPT_DIR!"

:: Step 1: Ensure uv is available
set "UV_CMD="
where uv >nul 2>&1
if !ERRORLEVEL! equ 0 (
    set "UV_CMD=uv"
) else (
    if exist "!SCRIPT_DIR!vendor\uv.exe" (
        set "UV_CMD=!SCRIPT_DIR!vendor\uv.exe"
    ) else if exist "!LOCALAPPDATA!\uv\bin\uv.exe" (
        set "UV_CMD=!LOCALAPPDATA!\uv\bin\uv.exe"
    ) else (
        echo [오류] uv.exe를 찾을 수 없습니다.
        echo vendor\uv.exe 파일이 있는지 확인하세요.
        pause
        exit /b 1
    )
)
echo [1/5] uv 확인 완료

:: Step 2: Create venv with Python 3.12
echo [2/5] Python 3.12 가상환경 생성 중...
set "PY312="
py -3.12 --version >nul 2>&1
if %ERRORLEVEL% equ 0 set "PY312=1"

if defined PY312 (
    "!UV_CMD!" venv "!SCRIPT_DIR!venv" --python "3.12" --quiet --allow-existing
) else (
    echo Python 3.12를 다운로드합니다 ^(인터넷 연결 필요^)...
    "!UV_CMD!" python install 3.12 --quiet
    if !ERRORLEVEL! neq 0 (
        echo [오류] Python 3.12 다운로드 실패.
        echo        Python 3.12를 먼저 설치하거나 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
    "!UV_CMD!" venv "!SCRIPT_DIR!venv" --python "3.12" --quiet --allow-existing
)
if !ERRORLEVEL! neq 0 (
    echo [오류] 가상환경 생성 실패
    pause
    exit /b 1
)
if not exist "!PYTHON_EXE!" (
    echo [오류] 가상환경 Python을 찾을 수 없습니다.
    echo        !PYTHON_EXE!
    pause
    exit /b 1
)

:: Step 3: Install packages from vendor/wheels (offline)
echo [3/5] 패키지 설치 중 ^(오프라인^)...
if exist "!WHEEL_DIR!" (
    dir /b "!WHEEL_DIR!\*.whl" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo [오류] vendor\wheels 폴더에 wheel 파일이 없습니다.
        echo        외부망 PC에서 download_wheels.bat을 다시 실행한 뒤 vendor 폴더를 복사하세요.
        pause
        exit /b 1
    )

    dir /b "!WHEEL_DIR!\setuptools-*.whl" >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo [오류] vendor\wheels에 setuptools wheel이 없습니다.
        echo        패키지 설치에는 setuptools가 필요합니다.
        echo        외부망 PC에서 최신 download_wheels.bat을 다시 실행한 뒤 vendor 폴더를 복사하세요.
        pause
        exit /b 1
    )

    "!UV_CMD!" pip install --python "!PYTHON_EXE!" ^
        --no-index --find-links "!WHEEL_DIR!" ^
        "setuptools>=61.0"
    if !ERRORLEVEL! neq 0 (
        echo [오류] setuptools 설치 실패
        pause
        exit /b 1
    )

    "!UV_CMD!" pip install --python "!PYTHON_EXE!" ^
        --no-build-isolation --no-index --find-links "!WHEEL_DIR!" ^
        -e ".[windows]"
) else (
    echo [경고] vendor\wheels 폴더 없음. 온라인 설치 시도...
    "!UV_CMD!" pip install --python "!PYTHON_EXE!" ^
        -e ".[windows]"
)
if !ERRORLEVEL! neq 0 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)

:: Step 4: Check Ollama
echo [4/5] Ollama 연결 확인 중...
curl -s --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [4/5] Ollama 연결 실패 ^(경고^):
    echo [경고] Ollama가 실행되지 않았습니다.
    echo        설치 후 ollama serve 를 실행하고 hermes.bat를 시작하세요.
) else (
    echo [4/5] Ollama 연결 확인 완료
)

:: Step 5: Print usage and finish
echo [5/5] 설치 완료
echo.
echo 사용법:
echo   hermes.bat              대화 시작
echo   hermes.bat init         프로젝트 컨텍스트 초기화
echo   hermes.bat chat .\src   디렉토리 컨텍스트로 대화 시작
echo.
pause
