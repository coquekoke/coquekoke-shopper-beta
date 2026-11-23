# SHOPPER 11.0: Actualizar el servicio Railway existente sin perder cestas

**No crees un servicio nuevo. No elimines el volumen. No copies bases SQLite al repositorio.**

1. En Railway, entra en el servicio actualmente **Active**, localiza el volumen persistente (montado en `/data`) y haz una copia de seguridad antes del cambio. Conserva las variables actuales (`SHOPPER_DB`, `SHOPPER_REMOTE`, `SHOPPER_REQUIRE_VOLUME`, `SHOPPER_CSRF_KEY`, `SHOPPER_SIGNUP_CODE` y la configuración de volumen y red). No publiques sus valores.
2. Descomprime el archivo `SHOPPER_v11_COMPLETA_RAILWAY.zip` o el parche. En GitHub, abre **la carpeta que Railway tiene configurada como Root Directory**. En tu caso, podría ser `/SHOPPER_v9_5_COMPLETA_DOCKER_RAILWAY`; verifica el nombre real en Settings → Source. **Sube el contenido dentro de esa carpeta, no la carpeta del ZIP dentro de otra carpeta**.
3. Deben aparecer juntos `Dockerfile`, `main.py`, `db.py`, `start.py`, `requirements.txt`, `static/v11.html`, `static/v11.js`, `static/v11.css` y `data/retail_official_snapshot_2026-11-23.json`. El catálogo JSON del directorio `data/` es necesario para que arranque.
4. Haz **Commit changes** en la rama conectada a Railway y espera el despliegue de ese commit. **No uses Redeploy sobre un commit antiguo.** El Dockerfile comprueba de forma explícita los archivos necesarios.
5. Revisa `https://TU-DOMINIO/health`. El resultado esperado es `"ok": true` y `"version": "11.0"`. La URL principal `/` muestra el nuevo diseño, `/previous` el de 10.0 y `/classic` la interfaz histórica.
6. Comprueba con dos cuentas que una cesta se comparte y recibe modificaciones, que las cestas antiguas no se han perdido y que una cesta semanal con lugar Casa tiene solo las tiendas de su red. Comprueba el aviso de origen y fecha de los precios.

## Si el despliegue falla

- Error de archivo `data/...json` ausente: mira si la carpeta `data/` está en GitHub dentro del Root Directory. Hemos corregido `.dockerignore` y `.gitignore` para no excluirla en bloque.
- Error por volumen: comprueba el montaje persistente `/data` y las variables anteriores. No desactives esa protección para conseguir que arranque.
- Sigue apareciendo versión 9.2 o 10.0: Railway está ejecutando un commit antiguo o el Root Directory incorrecto.
- Aparecen cestas vacías: **no borres el volumen**. Detén cambios y comprueba `SHOPPER_DB` y el montaje antes de seguir usando el sistema.

## Importante

Esta versión no sincroniza catálogos comerciales en tiempo real, no confirma stock local, no envía pedidos y no incluye pagos. Para uso público amplio faltan pruebas de seguridad, moderación y protección de datos.
