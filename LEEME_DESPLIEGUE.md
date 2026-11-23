# SHOPPER 9.3 — reparación del despliegue Railway

## Diagnóstico
En tu primera captura, el Docker build se cancelaba durante `[2/7] WORKDIR /app` en 4 segundos. Esto **no prueba** que `WORKDIR` esté mal ni que el código de SHOPPER falle; hace falta el log completo para conocer la causa. Este paquete cambia de constructor a **Railpack** y conserva la aplicación 9.2.

## Cambio mínimo en GitHub — si ya subiste SHOPPER 9.2
1. Abre tu repositorio privado `shopper-beta` en GitHub, raíz (misma carpeta de `main.py`).
2. **Elimina los archivos `Dockerfile` y `railway.json`** del repositorio haciendo un commit. No basta eliminarlos en tu PC.
3. Añade los **tres archivos** `railpack.json`, `.python-version` y `start.py` de este paquete, directamente a la raíz. Haz commit. `static/`, `db.py`, `main.py` y `requirements.txt` deben seguir ahí.
4. Railway → servicio `shopper-beta` → **Settings → Build → Builder = Railpack**. Comprueba Root Directory ` / ` o vacío y borra cualquier ruta de Dockerfile configurada. En **Settings → Deploy → Custom Start Command** deja vacío si Railpack lee `railpack.json`; si falla el descubrimiento, pon `python start.py`. Healthcheck: `/health`.
5. Si ya hay un volumen adjunto, **no lo borres**. Con SQLite usa una réplica y volumen `/data`.
6. Variables del servicio (secretos reales, nunca ejemplos):
   `SHOPPER_REMOTE=1`, `SHOPPER_DEMO=0`, `SHOPPER_REQUIRE_VOLUME=1`, `SHOPPER_DB=/data/shopper.sqlite3`, `SHOPPER_CSRF_KEY` (valor aleatorio de 40+ caracteres), `SHOPPER_SIGNUP_CODE` (valor aleatorio de 24+ caracteres). `RAILWAY_RUN_UID=0` solo si Railway lo requiere para permisos de escritura al volumen.
   Para generar secretos localmente: `python -c "import secrets; print(secrets.token_urlsafe(48)); print(secrets.token_urlsafe(32))"`
7. Despliega **el último commit**. Primero confirma `Build succeeded`; después revisa `Deploy Logs`. Solo cuando arranque y `/health` funcione, crea dominio HTTPS en Networking.

## Si no has subido nada a GitHub o el repo está desordenado
Puedes sustituir el código por **el contenido descomprimido de este ZIP** (no por el ZIP como archivo). Conserva tus variables y volúmenes Railway; nunca subas `.sqlite3`, `.env` o contraseñas al repositorio. No borres el volumen.

## Si reaparece `context canceled`
Copia el **Build Log completo** y confirma que el nuevo deploy dice **Railpack** (no Dockerfile/BuildKit). Si sigue cancelándose tras 1 intento de Railpack, consulta [Railway Status](https://status.railway.com/) y soporte con log y deployment ID; puede ser infraestructura o configuración del servicio.

## Alcance
Beta privada para pruebas con datos ficticios. Sin pagos ni preparación integrada con supermercados. Railway asignará la URL únicamente tras un despliegue correcto. Este paquete por sí solo no publica la aplicación ni protege por completo un servicio accesible en Internet. La autenticación necesita una auditoría antes de admitir datos personales reales.

Fuentes actuales: https://docs.railway.com/builds/railpack ; https://railpack.com/config/file ; https://docs.railway.com/volumes
