# SHOPPER 12.0 · Tus supers, tus cestas, tu gente

Versión de **beta privada**, ampliación compatible de SHOPPER 11.0, con las tablas de usuario y cestas anteriores. Funciones reales del servidor (FastAPI + SQLite):

- **Mapa y directorio** de establecimientos con coordenadas; permiso explícito del navegador para localizarte; orden por distancia geográfica estimada, no por tiempo de viaje. Importación OSM por archivo, o consulta puntual optativa para una beta pequeña.
- **Lugares y redes**: Casa, Oficina, Abuelos, etc. Cada lugar tiene su conjunto de tiendas preferidas, que puedes cambiar sin mover una cesta a otra ubicación.
- **Cestas tipo colecciones**: normales, recurrentes y eventos; las fechas de evento solo se ofrecen cuando se selecciona ese tipo. Varias tiendas y categorías cuando corresponda.
- **Productos comerciales**: muestra limitada de 37 fichas publicadas en webs DIA/Carrefour (23/11/2026), con enlaces a la fuente. No presupone surtido en las tiendas concretas que aparecen en el mapa.
- **Precio observado cerca**: muestra las últimas observaciones aportadas por usuarios, con fuente y fecha. No es una tarifa verificada ni un descuento activo.
- **Compra realizada**: puedes registrar cesta + extras y el coste real declarado; queda pendiente de recibir hasta que confirmas. Tras la recepción puedes añadir productos a la despensa voluntariamente o activar la opción por defecto. Operación idempotente.
- **Community**: publicaciones de tiendas/productos, reacciones, comentarios, denuncias, caducidad de observaciones. Los mensajes de amigos conservan su visibilidad privada.
- **Círculo**: ofrecimientos temporales de recados entre amistades aceptadas; no realiza pagos, no habilita reparto comercial ni expone personas vulnerables al público.
- **Compatibilidad**: interfaz 11 en `/previous` o `/v11`, versión 10 en `/v10` y clásica en `/classic`.

## Inicio local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python start.py
```

La beta local se abre en `http://127.0.0.1:8000` si el puerto predeterminado es 8000. El modo remoto en Railway requiere dominio HTTPS, volumen SQLite **/data** y variables de sesión/alta seguras (ver `GUIA_ACTUALIZACION_RAILWAY_12.md`).

## Conseguir supermercados de Madrid de manera legal

### Opción A. Descubrir las tiendas cercanas en el móvil

1. En Railway añade `SHOPPER_OSM_PILOT=1` a las variables del servicio (solo beta privada). Publica los cambios.
2. Entra en SHOPPER con tu cuenta y elige **Mi ubicación**. Safari pedirá permiso. Sin permiso puedes trabajar con tus lugares guardados o con Madrid centro como referencia de exploración (no se considera tu posición).
3. Selecciona un radio de **2–8 km** y pulsa **Descubrir tiendas OSM**. Esta consulta puntual externa requiere confirmación explícita; si no está disponible, puedes usar el directorio importado.
4. Guarda **varios supermercados** de referencia en cada lugar (Casa, Oficina, Casa de los abuelos...). La búsqueda posterior filtra cadenas por esos grupos, pero NO garantiza que cada SKU exista en cada tienda física.

No utilizar esta modalidad para millones de consultas. Los servidores públicos de Overpass y OpenStreetMap tienen una política de uso justo; para una aplicación comercial importa extractos OSM con licencia o contrata un proveedor y almacena tus geocodificaciones.

### Opción B. Importación offline de Madrid

1. Abre `docs/overpass_madrid.txt` en https://overpass-turbo.eu/ y exporta el resultado a **JSON**; la consulta puede ser grande, por lo que es posible que convenga dividirla por municipios, áreas o cuadrículas.
2. En la instalación local con una base SQLite propia de prueba:

```bash
SHOPPER_DB=/ruta/a/shopper.sqlite3 python tools/importar_osm_madrid.py /ruta/al/archivo.json
```

En Windows usa PowerShell: `$env:SHOPPER_DB='C:\\ruta\\shopper.sqlite3'; python tools/importar_osm_madrid.py C:\\ruta\\datos.json`.

3. Examina el número de tiendas importadas; comprueba muestras manualmente. La importación reconoce registros OSM `node`, `way` y `relation`, incluye referencias y preserva tiendas sin dirección completa como registros distintos etiquetados para comprobación.
4. Para producción, importa a una base de datos administrada mediante migraciones con copia de seguridad; **no sobrescribas la SQLite del volumen de Railway** sin control.

## Lo que no es esta versión

No está integrada con las cajas, ERP, inventario ni recogida de pedidos oficiales de DIA, Carrefour o cualquier cadena. No ofrece precios ni promociones en tiempo real garantizados. No permite cobrar ni asignar trabajo remunerado a shoppers. Para comercializar servicios hay que revisar normativa alimentaria, laboral, fiscal, consumo, pagos y protección de datos. La importación y redistribución comercial de catálogos de competidores requiere licencia; que tengan una web pública no da permiso para copiar sus bases.

## Pruebas

Ejecuta `pytest -q tests` (dependencias de desarrollo en `requirements-dev.txt`). Las nuevas tablas se crean sin eliminar información anterior. Los datos del navegador sin conexión no se guardan por arte de magia; hace falta que la conexión con el servidor vuelva.
