@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto :run

echo [MediaMeta] Creating virtual environment...
py -3.11 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :install

python -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :install

echo [MediaMeta] Could not create a virtual environment.
echo Install Python 3.11+ from python.org and run this file again.
pause
exit /b 1

:install
echo [MediaMeta] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [MediaMeta] Dependency install failed. See the messages above.
    pause
    exit /b 1
)

:run
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
