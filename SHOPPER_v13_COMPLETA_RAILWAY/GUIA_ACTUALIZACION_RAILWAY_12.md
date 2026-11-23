# Cómo actualizar Railway de SHOPPER 11 a 12, sin perder datos

1. **Copia de seguridad**: realiza snapshot/back-up del volumen persistente de tu servicio Railway, y anota la configuración actual. Conserva `SHOPPER_DB=/data/shopper.sqlite3` (o tu ruta previa válida). Una única réplica mientras SQLite siga en uso.
2. **Descarga el ZIP completo** o el parche; descomprímelo. Sube a la *misma carpeta raíz* de tu repositorio que Railway tiene seleccionada, sin anidar dentro de una nueva carpeta de versión. Al menos deben estar juntos: `Dockerfile`, `main.py`, `db.py`, `v12api.py`, `start.py`, `requirements.txt`, `static/`, `data/retail_official_snapshot_2026-11-23.json` y `tools/`.
3. **No subas** `*.sqlite3`, `*.db`, `.env`, claves, certificados, backups o códigos privados. `.gitignore` y `.dockerignore` lo impiden para archivos habituales, pero revísalo también antes del commit.
4. En Railway selecciona **Dockerfile**, conserva el **Root Directory**, las variables previas (`SHOPPER_REMOTE`, `SHOPPER_REQUIRE_VOLUME`, `SHOPPER_DB`, códigos privados y protección de sesión) y el volumen montado en `/data`. No borres el volumen.
5. *Opcional beta privada*: configura `SHOPPER_OSM_PILOT=1` y `SHOPPER_CONTACT_EMAIL` con un contacto genérico para identificar la consulta puntual Overpass; no habilites este modo para tráfico de muchos usuarios. Sin esta variable, la app funciona con el directorio que ya tengas guardado o importado.
6. Guarda el commit y **despliega el último commit**. No uses Redeploy de una versión antigua. En Build Logs el `RUN` verifica `static/v12.html`, `static/v12.js`, `static/v12.css` y `v12api.py` además de los archivos existentes.
7. Comprueba `https://TU-DOMINIO/health`: debe devolver `"version": "12.0"`. Abre `/` en Safari (debe cargar el diseño 12), ` /previous` para 11 y `/v10` para 10.
8. Prueba con **dos cuentas distintas**: crear una cesta compartida, modificarla desde otro móvil, seleccionar lugares/redes, registrar una compra con un artículo extra y confirmar su recepción antes de transferir a despensa. Los precios de la muestra siguen fechados y no equivalen a existencias reales.

### Diagnóstico
- `No module named uvicorn`: confirmar dependencias y commit correcto; el Dockerfile instala `requirements.txt`.
- `static/v12.html missing`: no se han subido los archivos dentro de la carpeta raíz esperada.
- `Falta un volumen persistente`: revisar volumen asociado y ruta `/data`; **no desactivar la protección para producción**.
- Error OSM 503: el importador externo beta está deshabilitado, la red está restringida o el servidor Overpass no responde; no implica caída de SHOPPER.
- Mapa sin teselas: comprueba conexión, bloqueo de CDN, CSP o proveedor cartográfico. La lista de tiendas sigue utilizable sin mapa.

**Límites:** la beta no ha recibido un pentest independiente y no es una plataforma de pagos ni un sistema comercial de logística. Antes de invitar a personas fuera de un grupo privado, revisar medidas antiabuso, RGPD y escalabilidad.
