@echo off
setlocal
cd /d "%~dp0"
echo -----------------------------------------
echo SHOPPER 8.0 - ALFA LOCAL
 echo No publiques el puerto 8000 en Internet.
echo -----------------------------------------
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Necesitas instalar Python 3.11+ desde python.org
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo No se han podido instalar dependencias.
  pause
  exit /b 1
)
set "SHOPPER_DEMO=1"
echo.
echo Abre http://127.0.0.1:8000 en tu navegador.
echo Pulsa Ctrl+C para detener el servidor.
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
