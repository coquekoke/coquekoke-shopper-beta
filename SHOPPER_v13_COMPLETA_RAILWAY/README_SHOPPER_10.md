# SHOPPER 10 — Compra primero, complejidad después

**Fecha de versión:** 23 de noviembre de 2026. **Tipo:** beta privada, no operativa como supermercado ni como plataforma de pedidos. No borra datos existentes.

## Qué cambia

1. **Nueva portada** en `/`: explorar productos sin registrarse, buscar, filtrar cadena/categoría y abrir fuente oficial.
2. **37 productos comerciales reales** (muestra editorial y fechada, no catálogo completo) procedentes de las páginas oficiales de DIA y Carrefour. Incluye precio **publicado en web**, no la oferta local ni existencia en una tienda concreta. No hay una API comercial concertada.
3. **Cestas**: acceso rápido a Actual, ilimitadas cestas adicionales, categorías semanales/mensuales/eventos, texto rápido, cantidades +/- y casillas de comprado, invitaciones privadas y copia a Actual.
4. **Tiendas y lugares**: DIA Santo Domingo y Sánchez Romero Moraleja Green como referencias del piloto, redes personales de tiendas y enlaces a catálogos web cuando existan. Tener una tienda en el directorio no le atribuye los precios de la web de su cadena.
5. **Foodpedia**: consulta por código EAN o nombre a Open Food Facts cuando `SHOPPER_OFF_USER_AGENT` está configurado y se dispone de conexión. Productos recuperados son fichas reales, no inventario comercial.
6. **Alta privada más clara**: el campo del código es visible en la creación de cuenta, y el servidor informa cuando el valor no coincide.
7. **Compatibilidad**: las funciones avanzadas anteriores permanecen en `/classic`, usando las mismas cuentas y base de datos.

## Qué falta (deliberadamente)

- Un catálogo completo y actualizado de cada tienda concreta; las webs de cadena no equivalen al stock local.
- Pedido directo al establecimiento, preparación por empleados, cobro y venta, contratación de shoppers.
- Comparador transversal por equivalencias verificadas, descuentos individuales y aplicación automática de ofertas.
- Fichas de todos los supermercados de Madrid y geolocalización comercial validada.
- Auditoría de seguridad y privacidad para lanzar públicamente.

## Abrir y probar

### Vista previa sin servidor
Abre `SHOPPER_10_VISTA_PREVIA.html` desde la entrega: prueba la búsqueda y los filtros del catálogo. **No guarda cestas ni conecta cuentas.**

### Aplicación real local
```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python start.py
```
Abre `http://127.0.0.1:8000` o el puerto configurado. Las cuentas y los datos persisten en SQLite.

### Actualizar tu Railway sin perder los datos

1. **Haz una copia del volumen persistente** (y de tu repositorio GitHub) antes de modificar código.
2. En el repositorio existente, trabaja en **el mismo directorio que contiene `Dockerfile`, `main.py`, `db.py` y `static/`**. Si la raíz configurada en Railway es `/SHOPPER_v9_5_COMPLETA_DOCKER_RAILWAY`, actualiza los archivos **dentro** de esa carpeta. No subas un ZIP sin descomprimir ni crees una subcarpeta extra.
3. **Opción fácil:** sube y sobrescribe desde el parche: `main.py`, `db.py`, `static/v10.html`, `static/v10.js`, `static/v10.css`, `data/retail_official_snapshot_2026-11-23.json`. Para deploy completo también puedes actualizar Dockerfile si haces lo mismo dentro de la carpeta correcta.
4. Haz un commit en la rama conectada a Railway. No borres tu volumen, tus variables ni cambies su ruta `/data`.
5. Railway debería reconstruir el mismo servicio. Comprueba `/health`: `version` debe ser `10.0`; entra en `/` para ver el nuevo diseño. En `/classic` permanecerá la interfaz anterior.
6. **Opcional:** en las variables privadas de Railway, añade `SHOPPER_OFF_USER_AGENT` con el formato `SHOPPER/10.0 (correo-real-de-contacto@dominio.tld)` para habilitar búsquedas por nombre y EAN en Open Food Facts. Nunca uses una dirección falsa o de terceros. No introduzcas el código privado de registro en esta variable.
7. Prueba una cesta con dos cuentas y confirma que la lista guarda los cambios tras recargar.

**No se cambian** `SHOPPER_DB`, `SHOPPER_REMOTE`, `SHOPPER_REQUIRE_VOLUME`, `SHOPPER_SIGNUP_CODE`, `SHOPPER_CSRF_KEY` ni el volumen. No envíes secretos por chat.

### Diagnóstico
- `GET /health`: versión y servidor.
- `GET /api/retail/catalog`: 37 fichas y sus fuentes, sin login.
- Si te aparece un catálogo vacío, comprueba que la carpeta `data/` se haya subido.
- Si no puedes registrarte, revisa `SHOPPER_SIGNUP_CODE` activo en Variables y la entrada en el formulario `Crear cuenta` (no `Entrar`).
- Si Foodpedia indica que falta configuración, define `SHOPPER_OFF_USER_AGENT`. No afecta al resto del catálogo.

### Pruebas
```sh
pip install -r requirements-dev.txt
python -m pytest -q
```
Se han superado 40 pruebas de API y regresión en el entorno de desarrollo. `node --check static/v10.js` también pasa. **No se ha conseguido ejecutar una prueba visual automatizada:** la política del navegador de esta sesión bloquea incluso direcciones locales; debes revisar la vista previa en tu navegador e iPhone tras desplegar.

## Fuentes y atribución

- [DIA — Arroz](https://www.dia.es/arroz-pastas-y-legumbres/arroz/c/L2042)
- [DIA — Leche](https://www.dia.es/huevos-leche-y-mantequilla/leche/c/L2051)
- [Carrefour — La despensa](https://www.carrefour.es/supermercado/la-despensa-carrefour/F-13ji8Z10si/c)
- [Carrefour — Huevos](https://www.carrefour.es/supermercado/productoscrf-huevos-vinagre-blanco/F-1kc6vZ16muZ11dc/g)
- [Carrefour — Aceite de oliva virgen extra](https://www.carrefour.es/supermercado/productoscrf-carrefour-aceite-de-oliva-virgen-extra-lugar-fresco-y-seco-mollete/F-1kc6vZ10siZp646Z11fdZ1qgx/g)
- [Open Food Facts](https://world.openfoodfacts.org/) · ODbL, atribución y condiciones de reutilización.

**No se debe utilizar el piloto para redistribuir de forma masiva catálogos ajenos sin licencia.**
