@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === SHOPPER 9.0 - Servidor familiar para iPhone ===
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 (echo Instala Python 3.11 o posterior y marca Add to PATH & pause & exit /b 1)
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo Error instalando dependencias & pause & exit /b 1)
.venv\Scripts\python.exe tools\start_private.py
pause
