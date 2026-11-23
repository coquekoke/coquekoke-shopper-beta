# SHOPPER 13.0 — Actualización sin perder datos

## Antes de subir archivos

1. Haz una **copia de seguridad del volumen** de Railway (SQLite en `/data`). No borres el servicio, las variables ni el volumen.
2. Abre en Railway la pestaña **Settings → Source → Root Directory**. Asegúrate de que sabes si tu repositorio contiene los archivos en raíz o dentro de una subcarpeta. Actualiza **esa carpeta**, sin anidar otro ZIP.
3. El paquete completo contiene `main.py`, `db.py`, `v12api.py`, `v13api.py`, `requirements.txt`, `Dockerfile`, `start.py`, `static/` y `data/`. Debes mantener esa estructura.

## Despliegue

1. Sube al repositorio conectado a Railway los archivos del paquete descomprimido (o el parche de V12 → V13).
2. Confirma que se incluyen `static/v13.html`, `static/v13.js`, `static/v13.css` y `v13api.py`.
3. Haz **Commit changes** y comprueba el **hash del nuevo commit** en Railway. No uses «Redeploy» de un despliegue antiguo.
4. Conserva los valores de `SHOPPER_REMOTE=1`, `SHOPPER_REQUIRE_VOLUME=1`, `SHOPPER_DB=/data/shopper.sqlite3` (si esta es tu ruta real), `SHOPPER_DEMO=0`, `SHOPPER_CSRF_KEY` y `SHOPPER_SIGNUP_CODE`.
5. **Opcional, recomendado antes de guardar tarjetas:** crea la variable privada `SHOPPER_CARDS_KEY` con un valor aleatorio largo, de al menos 32 caracteres, y consérvala estable. Si no existe, las tarjetas se cifran con una clave separada derivada de `SHOPPER_CSRF_KEY`. **No cambies esas claves sin un plan de migración**: perderías acceso a los códigos cifrados. No me envíes ninguna clave.
6. Comprueba `https://TU-DOMINIO/health`, que debe indicar `"version":"13.0"`. La raíz muestra el nuevo menú «Mis tarjetas» y «Recetas a cesta». La anterior versión permanece en `/v12`.

## Prueba funcional

- Inicia sesión y añade una **tarjeta de prueba** con un código estático propio (no una tarjeta bancaria ni datos de terceros). Verifica visualización y borrado.
- Crea una receta con `200 g arroz`, `250 ml leche entera` y `2 huevos`. Cambia raciones y compara DIA y Carrefour.
- Pulsa «Convertir en cesta»; confirma que ha generado una cesta ocasional nueva sin enviar pedido ni realizar un cargo.
- Comprueba que siguen funcionando cestas, despensa, lugares, social y mapa.

## Privacidad y legalidad

- El número de tarjeta se almacena **cifrado en SQLite**; nombre de programa y últimas 4 posiciones se conservan sin cifrar para identificarla. El cifrado es una capa de seguridad, no sustituye auditoría ni protección del servidor. No almacenes credenciales de acceso, PIN, códigos de un solo uso o tarjetas de pago.
- Los códigos dinámicos, cupones y saldos exigen la aplicación oficial y, en algunos casos, controles del operador. Un código mostrado en SHOPPER **no tiene validez garantizada en caja**.
- El importador acepta ingredientes pegados o JSON-LD de tipo `Recipe`. Guarda la URL de origen, **pero no descarga contenido arbitrario** de páginas de terceros.
- Los precios son una **muestra editorial fechada del 23/11/2026** (solo DIA y Carrefour) y no reflejan necesariamente surtido, promociones o existencia en cada tienda física.
- Solo un único proceso/replica debe usar la SQLite existente. Mantén backups y no registres códigos sensibles en logs.
