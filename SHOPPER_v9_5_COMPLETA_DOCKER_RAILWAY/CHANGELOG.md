# 9.3 · Despliegue alternativo

- Eliminados Dockerfile y railway.json para construir con Railpack.
- Añadidos railpack.json y lanzador start.py que lee PORT de Railway.
- Conservada la aplicación y sus tests de v9.2.
- Guía de reparación segura de despliegue sin pérdida de base de datos.

## 9.4 — Railway Uvicorn
- Paquete mínimo incorpora ahora requirements.txt (omitido anteriormente).
- Arranque detecta virtualenv Python de Railpack si el Python inicial no tiene dependencias.
- Guía específica para la verificación Build Logs / Root Directory.
