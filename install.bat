@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo === Hermes Windows Installer ===
echo.

:: Step 1: Ensure uv is available
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if exist "%~dp0vendor\uv.exe" (
        echo uv를 설치합니다...
        copy "%~dp0vendor\uv.exe" "%LOCALAPPDATA%\uv\bin\uv.exe" >nul 2>&1
        set "PATH=%LOCALAPPDATA%\uv\bin;%PATH%"
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
uv python install 3.12 --quiet
uv venv "%~dp0venv" --python 3.12 --quiet
if %ERRORLEVEL% neq 0 (
    echo [오류] 가상환경 생성 실패
    pause
    exit /b 1
)

:: Step 3: Install packages from vendor/wheels (offline)
echo [3/5] 패키지 설치 중 (오프라인)...
if exist "%~dp0vendor\wheels" (
    "%~dp0venv\Scripts\python.exe" -m pip install --quiet ^
        --no-index --find-links "%~dp0vendor\wheels" ^
        -e "%~dp0.[windows]"
) else (
    echo [경고] vendor\wheels 폴더 없음. 온라인 설치 시도...
    "%~dp0venv\Scripts\python.exe" -m pip install --quiet -e "%~dp0.[windows]"
)
if %ERRORLEVEL% neq 0 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)

:: Step 4: Check Ollama
echo [4/5] Ollama 연결 확인 중...
curl -s --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [경고] Ollama가 실행되지 않았습니다.
    echo        설치 후 ollama serve 를 실행하고 hermes.bat를 시작하세요.
) else (
    echo [4/5] Ollama 연결 확인 완료
)

:: Step 5: Confirm hermes.bat exists
echo [5/5] 설치 완료
echo.
echo 사용법:
echo   hermes.bat              대화 시작
echo   hermes.bat init         프로젝트 컨텍스트 초기화
echo   hermes.bat chat .\src   디렉토리 컨텍스트로 대화 시작
echo.
pause
