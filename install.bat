@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================================
echo SongForge-MCP installer (ACE-Step 1.5 backend)
echo ============================================================

REM ---- Step 1: Python bootstrap ----
where python >nul 2>&1
if errorlevel 1 (
    echo Python not found on PATH. Installing Python 3.11...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_python.ps1"
    if errorlevel 1 (
        echo Failed to install Python automatically.
        echo Install Python 3.11+ manually from python.org and re-run this script.
        exit /b 1
    )
    echo Python installed. You may need to restart this terminal for PATH changes
    echo to take effect before re-running this script.
    exit /b 0
)

REM ---- Step 2: disk space check (ACE-Step's checkpoint alone is ~28GB) ----
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check_disk_space.ps1" -RequiredGB 40
if errorlevel 1 (
    echo Not enough free disk space to continue safely ^(need ~40GB free^).
    echo This project hit 100%% disk usage once already from this same download -
    echo free up space first ^(pip cache purge, old Docker/WSL bloat, etc.^).
    exit /b 1
)

REM ---- Step 3: this server's own venv ----
echo.
echo Setting up songforge-mcp's own venv...
python -m venv .venv
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
".venv\Scripts\python.exe" -m playwright install chromium

REM ---- Step 4: ACE-Step 1.5 checkout ----
if "%SONGFORGE_ACESTEP_HOME%"=="" (
    set "ACESTEP_DEST=%~dp0..\ACE-Step-1.5"
    echo.
    echo SONGFORGE_ACESTEP_HOME not set - cloning ACE-Step 1.5 to !ACESTEP_DEST!...
    if not exist "!ACESTEP_DEST!" (
        git clone https://github.com/ace-step/ACE-Step-1.5.git "!ACESTEP_DEST!"
    )
) else (
    set "ACESTEP_DEST=%SONGFORGE_ACESTEP_HOME%"
)

echo.
echo Setting up ACE-Step 1.5's own venv - this is the slow part
echo ^(torch + flash-attn are large downloads, checkpoint download is ~28GB
echo   and happens on first server launch, not during this step^)...
pushd "%ACESTEP_DEST%"
python -m venv .venv
REM Pinned exactly - do NOT let this float to a newer torch. A newer torch
REM breaks the prebuilt flash-attn wheel below, which in turn breaks
REM nano-vllm's CUDA graph capture path (a much worse failure than just
REM losing the speed benefit - confirmed by testing).
".venv\Scripts\python.exe" -m pip install torch==2.7.1+cu128 torchvision==0.22.1+cu128 torchaudio==2.7.1+cu128 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (
    echo torch install failed - if this GPU isn't cu128-compatible, see
    echo docs/INSTALLATION.md for alternatives. Aborting.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m pip install -e "acestep\third_parts\nano-vllm"
".venv\Scripts\python.exe" -m pip install -e . --no-deps
popd

setx SONGFORGE_ACESTEP_HOME "%ACESTEP_DEST%"
set "SONGFORGE_ACESTEP_HOME=%ACESTEP_DEST%"

REM ---- Step 5: stem separator - isolated venv, unrelated dependency needs ----
echo.
echo Setting up stem-separator venv (isolated from ACE-Step's - different,
echo unrelated dependencies, matching this project's per-tool venv convention)...
set "SEPARATOR_HOME=%~dp0.separator_env"
python -m venv "%SEPARATOR_HOME%"
"%SEPARATOR_HOME%\Scripts\python.exe" -m pip install audio-separator onnxruntime-gpu
setx SONGFORGE_SEPARATOR_PYTHON "%SEPARATOR_HOME%\Scripts\python.exe"

REM ---- Step 6: yt-dlp (already a dependency of this server's own venv) ----
setx SONGFORGE_YTDLP_PYTHON "%~dp0.venv\Scripts\python.exe"

echo.
echo ============================================================
echo Done.
echo   SONGFORGE_ACESTEP_HOME     = %ACESTEP_DEST%
echo   SONGFORGE_SEPARATOR_PYTHON = %SEPARATOR_HOME%\Scripts\python.exe
echo   SONGFORGE_YTDLP_PYTHON     = %~dp0.venv\Scripts\python.exe
echo.
echo These are now set as permanent user environment variables (setx).
echo Restart your terminal / Claude Desktop for them to take effect.
echo.
echo First real generation will trigger ACE-Step's ~28GB checkpoint download
echo (XL-SFT + 5Hz LM + VAE) - this only happens once.
echo.
echo Run 'songforge-mcp' (inside .venv) to start the server.
echo ============================================================
