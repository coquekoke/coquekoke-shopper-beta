# SHOPPER 9.2 — instalar en Railway desde GitHub (beta familiar)

**Resultado deseado:** una URL HTTPS accesible desde Safari en tu iPhone 15 y en el móvil de otra persona, sin tener tu ordenador encendido y sin instalar Tailscale. **No se ha desplegado todavía:** los siguientes pasos los harás tú en tus cuentas, o un desarrollador autorizado.

## 0. Precauciones

Esta versión sigue siendo una **alfa privada**, sin auditoría profesional, recuperación de cuentas por correo, 2FA ni sistema de pagos. Railway ofrece una URL pública: un desconocido podría llegar al formulario de inicio de sesión, aunque no debería acceder a datos sin credenciales. Para máxima privacidad utiliza Tailscale o añade una capa Cloudflare Access antes de abrir el proyecto a personas reales. Usa nombres de prueba y evita direcciones, datos sensibles o fotografías de documentos. No publiques código de altas ni secretos.

## 1. Subir el código a GitHub (repositorio PRIVADO)

1. Crea una cuenta en https://github.com si no tienes.
2. Crea un repositorio nuevo llamado `shopper-beta` con visibilidad **Private**.
3. Sube **los archivos descomprimidos de esta carpeta** (incluidas `main.py`, `db.py`, `Dockerfile`, `railway.json`, `requirements.txt`, `static/`, `tools/`). Puedes usar GitHub Desktop para publicarlo o subir los archivos a través de GitHub. **No subas el ZIP como un único archivo**: Railway necesita encontrar el Dockerfile y el código en la raíz del repositorio.
4. Comprueba que no has incluido `.shopper_private.json`, `data/`, `*.sqlite3`, `.env` o secretos. El fichero `.gitignore` ayuda, pero verifica antes de publicar.

## 2. Crear el servicio en Railway

1. En https://railway.com inicia sesión, crea `New Project` y selecciona `Deploy from GitHub repo` → `shopper-beta`. Autoriza a Railway el acceso a ese repositorio privado.
2. Railway detectará el `Dockerfile`; si no, selecciona Dockerfile en Build.
3. Antes de habilitar el sitio para usuarios, añade **un volumen persistente al servicio** con mount path exactamente `/data`. Esto es **imprescindible** para la SQLite.
4. En el panel de **Variables** del servicio añade estas entradas (las dos claves deben ser aleatorias y privadas):

```dotenv
SHOPPER_REMOTE=1
SHOPPER_DEMO=0
SHOPPER_REQUIRE_VOLUME=1
SHOPPER_DB=/data/shopper.sqlite3
SHOPPER_CSRF_KEY=PEGA_AQUI_UN_SECRETO_ALEATORIO_DE_40_O_MAS_CARACTERES
SHOPPER_SIGNUP_CODE=PEGA_AQUI_OTRO_CODIGO_ALEATORIO_DE_24_O_MAS_CARACTERES
RAILWAY_RUN_UID=0
```

Para generar los dos valores aleatorios, puedes ejecutar en tu ordenador:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48)); print(secrets.token_urlsafe(32))"
```

Copia cada resultado en su variable correspondiente. No uses los textos de ejemplo ni reutilices ambas claves. Railway monta los volúmenes como `root`; su documentación indica `RAILWAY_RUN_UID=0` al usar contenedores con usuario sin privilegios. Este ajuste reduce el aislamiento del proceso: úsalo solo para la beta pequeña hasta migrar a PostgreSQL u otra arquitectura que permita usuario sin privilegios.

5. Aplica los cambios y despliega. Si olvidaste el volumen, SHOPPER **rechazará el arranque**; esto es intencionado para no perder datos.
6. En el servicio ve a **Settings → Networking → Public Networking → Generate Domain**. Copia el dominio `https://...up.railway.app` real que te asigne Railway. No podemos generarlo sin entrar en tu cuenta.
7. Abre `https://TU_DOMINIO.up.railway.app/health` y comprueba `ok:true`. Después abre la raíz. Si obtienes un error, revisa los registros del despliegue.

## 3. Instalar en tu iPhone y compartir con un familiar

1. Safari → abre tu **URL HTTPS** de Railway.
2. Pulsa **Crear cuenta** e introduce el código privado `SHOPPER_SIGNUP_CODE`, un usuario y una contraseña única de 12+ caracteres. No compartas tu contraseña.
3. Comparte la URL por mensaje a tu familiar **y por separado** el código privado de alta (solo personas de confianza). Esa persona crea su propia cuenta.
4. Dentro de SHOPPER crea una cesta, entra en **Mis cestas → Invitar**, comparte el código de invitación de cesta con tu familiar y deja que lo canjee. Comprobad desde dos móviles que ambos podéis modificarla.
5. Safari → Compartir → Añadir a pantalla de inicio → Abrir como app web (si aparece).

## 4. Mantener la app y no perder datos

- **Volumen obligatorio:** solo un servicio/instancia, sin réplicas (SQLite no escala con múltiples instancias).
- **Backups:** configura backups de volumen en Railway y descarga periódicamente copias verificadas en almacenamiento cifrado. Prueba restaurar una copia antes de invitar a más personas. Los backups no son automáticos por tener un volumen.
- **Coste:** revisa el plan y el gasto visible en Railway. Su plan Free tiene créditos y límites que pueden no cubrir un servicio siempre encendido; Hobby tiene un mínimo de 5 USD/mes, sujeto a cambios.
- **Actualizaciones:** no borres el volumen ni cambies `SHOPPER_DB` entre despliegues. Sube el código actualizado a GitHub para activar un nuevo deploy.
- **Rotación:** si se filtra el código de alta, reemplaza `SHOPPER_SIGNUP_CODE`. Si se filtra la clave CSRF, reemplázala e invalida sesiones si es necesario.
- **Privacidad:** informa a quienes participan sobre cómo se usan los datos; todavía no está preparado para un lanzamiento público ni para datos sensibles.

## 5. Solución de errores comunes

- **Arranque fallido por volumen:** revisa que hayas añadido el disco, que monte en `/data` y que `SHOPPER_DB=/data/shopper.sqlite3`; revisa `RAILWAY_RUN_UID=0`.
- **No responde el dominio:** Railway debe asignar un dominio y el contenedor debe arrancar con `0.0.0.0` y `PORT` (incluido en Dockerfile).
- **403 por origen/CSRF:** abre únicamente la URL HTTPS correcta, evita redirecciones a HTTP y reingresa al formulario.
- **Datos perdidos:** detén la beta y comprueba volumen y backups; no recrees una base vacía sobre una existente.
- **Cuenta creada pero otra persona no ve tu cesta:** son cuentas separadas; envía la invitación específica desde Mis cestas.

## Documentación oficial (consultada 23-11-2026)

- https://railway.com/guides/fastapi
- https://docs.railway.com/volumes
- https://docs.railway.com/networking/domains/working-with-domains
- https://railway.com/pricing
- https://support.apple.com/en-ie/guide/iphone/iph42ab2f3a7/27/ios/27
