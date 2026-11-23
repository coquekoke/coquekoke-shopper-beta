@echo off
cd /d "%~dp0"
where python >nul 2>&1 || (echo Instala Python 3.11+ desde python.org & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
.venv\Scripts\python.exe tools\start_wifi.py
pause
