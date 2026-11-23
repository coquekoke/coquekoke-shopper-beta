# SHOPPER 9.5 — instalación determinista de dependencias para Railway
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Instalar antes de copiar el resto del codigo: fallo visible en Build Logs si falta uvicorn.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt \
    && python -c "import fastapi, uvicorn, pydantic; print('SHOPPER DEPENDENCIAS OK: uvicorn', uvicorn.__version__)"

COPY . /app
# No repetir el error anterior por copiar static/ cuando falta en el repositorio.
# Ahora comprobaremos la estructura y fallaremos con un mensaje explicito en los Build Logs.
RUN python -c "from pathlib import Path; required=['main.py','db.py','start.py','static/index.html','static/app.js','static/style.css']; missing=[x for x in required if not Path(x).is_file()]; assert not missing, 'Archivos faltantes en GitHub: '+', '.join(missing)"

# Railway pasa PORT en tiempo de ejecucion; start.py ya usa 0.0.0.0 y PORT.
CMD ["python", "start.py"]
