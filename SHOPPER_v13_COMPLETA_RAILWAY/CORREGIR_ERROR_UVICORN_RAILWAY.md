# SHOPPER 9.4 — Corrección del fallo `No module named uvicorn` en Railway

## Qué hemos comprobado
El `requirements.txt` del paquete completo 9.3 **ya contiene `uvicorn>=0.30,<1`**. Pero el parche MINIMO 9.3 entregado anteriormente **no incorporaba `requirements.txt`**. Si tu repositorio GitHub no tenía ese archivo, Railpack no tuvo dependencias que instalar. También es posible que el directorio raíz del servicio no coincida con la ubicación del archivo, o que el intérprete usado al arrancar sea distinto del usado al instalar.

## Pasos en GitHub (sin borrar Railway ni el volumen)
1. Abre el repositorio conectado a Railway. En su raíz deben existir juntos: `main.py`, `db.py`, `requirements.txt`, `start.py`, `railpack.json`, `.python-version` y la carpeta `static/` con `index.html`, `app.js` y `style.css`.
2. Sube **los cinco archivos de este parche** a la **raíz** del repositorio y haz **Commit changes**. Confirma que se vea `requirements.txt` (no un `requirements.txt.txt`).
3. Railway > servicio > **Settings > Build**: Builder Railpack; **Root Directory** vacío o `/` si los archivos están en la raíz. No debe haber un Dockerfile obligatorio ni custom build command que omita instalar dependencias.
4. Railway > **Settings > Deploy**: deja vacío Custom Start Command para que lea `railpack.json`, o escribe `python start.py` si necesitas fijarlo. Healthcheck `/health`.
5. Despliega el nuevo commit. En **Build Logs**, busca la instalación de paquetes desde `requirements.txt` (FastAPI y Uvicorn). Si no aparece, el error está en el contexto de compilación, no en el arranque.
6. En **Deploy Logs**, verifica que el servidor inicia sin `ModuleNotFoundError`. Después comprueba `/health` desde la URL HTTPS.

## Si sigue saliendo `ModuleNotFoundError`
- Si Build Logs no muestra `requirements.txt`, envía captura de **raíz del repo GitHub** y **Build Logs** para revisar Root Directory, no hace falta tocar secretos.
- Si Build Logs instala Uvicorn pero `python start.py` no lo encuentra, este nuevo `start.py` busca los entornos virtuales habituales de Railpack (`/app/venv`, `/app/.venv`, `/opt/venv`), comprueba qué Python puede importar Uvicorn y lo utiliza.
- Si el siguiente fallo se refiere a `StaticFiles(directory=...)`, falta la carpeta `static/` en GitHub: sube sus archivos del ZIP completo 9.4.
- Si el servidor indica que falta el volumen o secretos, **no desactives las protecciones**: comprueba el volumen `/data` y las variables privadas existentes (`SHOPPER_REMOTE`, `SHOPPER_DEMO`, `SHOPPER_REQUIRE_VOLUME`, `SHOPPER_DB`, `SHOPPER_CSRF_KEY`, `SHOPPER_SIGNUP_CODE`).

## Qué NO hacer
No elimines tu servicio Railway, no borres su volumen, no subas bases SQLite ni claves a GitHub, y no uses `pip install uvicorn` como comando de arranque en producción. Es mejor resolver la instalación durante el build. Mantén una sola réplica mientras uses SQLite.

## Alcance de la comprobación
Los archivos de esta entrega se han verificado localmente y con las pruebas automatizadas existentes de SHOPPER. **No tenemos acceso a tu repositorio privado ni a Railway para verificar que la versión publicada sea exactamente la misma**. Las incidencias de arranque en producción dependen de la configuración real del servicio.

Documentación: https://railpack.com/languages/python/ ; https://docs.railway.com/builds/railpack
