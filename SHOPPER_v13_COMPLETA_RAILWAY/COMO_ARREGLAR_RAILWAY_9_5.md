# SHOPPER 9.5 — Reparar Railway de forma definitiva (beta privada)

## 1. Diagnostico comprobable
Tu log todavia muestra `File /app/start.py, line 3: import uvicorn`. Eso corresponde al `start.py` de 9.3. En 9.4 y 9.5, la linea 3 es `import os`. Por tanto, el contenedor que ha fallado **no contiene nuestro archivo actualizado**. Esto indica que Railway ha construido un commit distinto, una carpeta raiz incorrecta o que el commit nuevo no llego a la rama conectada.

## 2. Subir bien el proyecto a GitHub (no subir el .zip tal cual)
1. Descarga el ZIP COMPLETO, **descomprime** y abre `SHOPPER_v9_5_DOCKER_PARA_RAILWAY` en tu ordenador.
2. En GitHub abre el repositorio realmente conectado a Railway (comprueba **Settings > Source** en Railway). Selecciona su rama (normalmente `main`).
3. Actualiza la **raiz** del repositorio con el **contenido** de la carpeta descomprimida, NO con la carpeta contenedora ni con un ZIP como archivo. Si prefieres, usa GitHub Desktop para copiar todos los archivos y confirmar el commit.
4. En la raiz deben verse `Dockerfile`, `requirements.txt`, `start.py`, `main.py`, `db.py`, y el directorio `static` con `index.html`, `app.js`, `style.css`.
5. Borra del repositorio los archivos antiguos `railpack.json` y `railway.json`, si existen, y cualquier Dockerfile anterior. **No borres tu volumen Railway ni tus datos persistentes.**
6. Verifica entrando en `start.py` de GitHub: comienza con `SHOPPER launcher: prefers` y en la linea 3 debe aparecer `import os`, **no** `import uvicorn`. Comprueba el hash del ultimo commit.

## 3. Railway — sin tocar datos persistentes
1. En el servicio que falla entra en **Settings > Source** y confirma repositorio y rama.
2. En **Settings > Build**, usa **Dockerfile** y ruta `Dockerfile` en la raiz. **Root Directory** vacio o `/` si los archivos estan en la raiz. No debe haber un Custom Build Command antiguo.
3. En **Settings > Deploy**, deja vacio el comando de inicio personalizado para usar el `CMD` del Dockerfile, o establece `python start.py`. Healthcheck `/health`.
4. Mantén el volumen montado en `/data` y las variables privadas **existentes** de SHOPPER (`SHOPPER_REMOTE=1`, `SHOPPER_DEMO=0`, `SHOPPER_REQUIRE_VOLUME=1`, `SHOPPER_DB=/data/shopper.sqlite3`, `SHOPPER_CSRF_KEY`, `SHOPPER_SIGNUP_CODE`). No reveles secretos. Usa una replica con SQLite.
5. Haz commit de los cambios y espera a que Railway construya ese **mismo commit**. No pulses Redeploy de un despliegue antiguo: eso puede ejecutar el mismo codigo viejo.

## 4. Como reconocer que esta arreglado
**Build Logs** deben mostrar algo parecido a: `SHOPPER DEPENDENCIAS OK: uvicorn 0.x` y el comando `pip install ... -r /app/requirements.txt`.
**Deploy Logs** ya no deben contener `ModuleNotFoundError`. Si aparece un nuevo error de volumen o claves, significa que hemos pasado la fase de dependencias: revisa `/data` y las variables, sin desactivar protecciones.
Abre `https://TU_DOMINIO/health` solo cuando Railway anuncie un despliegue activo.

## 5. Limites
No hemos desplegado en tu cuenta Railway ni comprobado Docker dentro de Railway. El codigo ha pasado las pruebas locales de la aplicacion y verificacion de archivos. Este arreglo corrige la fase de instalacion pero no sustituye la revision de seguridad previa a un lanzamiento publico. El contenido de esta entrega no incluye bases SQLite ni contrasenas.

Documentacion oficial: https://docs.railway.com/builds/railpack ; https://docs.railway.com/builds/build-configuration ; https://docs.railway.com/deployments/start-command
