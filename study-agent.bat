@echo off
setlocal
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "LITELLM_LOCAL_MODEL_COST_MAP=True"
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\.venv\Scripts\python.exe" -m study_agent.cli %*
    exit /b %ERRORLEVEL%
)

if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\venv\Scripts\python.exe" -m study_agent.cli %*
    exit /b %ERRORLEVEL%
)

python -m study_agent.cli %*
exit /b %ERRORLEVEL%
