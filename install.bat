@echo off
setlocal

cd /d "%~dp0"

echo Setting up vocal-synth-mcp...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -e ".[dev]"

if "%VOCAL_SYNTH_DIFFSINGER_HOME%"=="" (
    echo.
    echo VOCAL_SYNTH_DIFFSINGER_HOME is not set.
    echo Clone openvpi/DiffSinger separately, install its own requirements.txt
    echo ^(PyTorch ^>=2.4.0 matched to your CUDA version^), then set:
    echo   setx VOCAL_SYNTH_DIFFSINGER_HOME "C:\path\to\DiffSinger"
    echo See docs\INSTALLATION.md for full steps.
)

echo Done. Run 'vocal-synth-mcp' ^(inside .venv^) to start the server.
