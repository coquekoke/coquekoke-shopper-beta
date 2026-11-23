# SHOPPER 13 — instalación determinista de dependencias para Railway
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Instalar antes de copiar el resto del codigo: fallo visible en Build Logs si falta uvicorn.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt \
    && python -c "import fastapi, uvicorn, pydantic, cryptography, qrcode, reportlab; print('SHOPPER DEPENDENCIAS OK: uvicorn', uvicorn.__version__)"

COPY . /app
# No repetir el error anterior por copiar static/ cuando falta en el repositorio.
# Ahora comprobaremos la estructura y fallaremos con un mensaje explicito en los Build Logs.
RUN python -c "from pathlib import Path; required=['main.py','db.py','start.py','static/index.html','static/app.js','static/style.css','static/v10.html','static/v10.js','static/v10.css','static/v11.html','static/v11.js','static/v11.css','static/v12.html','static/v12.js','static/v12.css','static/v13.html','static/v13.js','static/v13.css','v12api.py','v13api.py','data/retail_official_snapshot_2026-11-23.json']; missing=[x for x in required if not Path(x).is_file()]; assert not missing, 'Archivos faltantes en GitHub: '+', '.join(missing)"

# Railway pasa PORT en tiempo de ejecucion; start.py ya usa 0.0.0.0 y PORT.
CMD ["python", "start.py"]
