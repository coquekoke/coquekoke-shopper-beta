# SHOPPER 11.0 — Tu biblioteca de compras, conectada con lugares

**Versión beta privada | España | Noviembre de 2026**

SHOPPER une cestas personales, redes locales de tiendas, listas colaborativas y un círculo de ayuda voluntaria. Esta entrega está pensada para **validación con un grupo pequeño**: no es un supermercado online, no recibe pedidos comerciales, no gestiona pagos y no afirma existencias en tiempo real.

## Lo nuevo, de verdad

- **Biblioteca de cestas** tipo colección visual (portada de emoji, color, nombre, temas seleccionables, cestas ilimitadas). Conserva la cesta `Actual`, las semanales, mensuales, ocasionales y de eventos.
- **Formularios contextuales** en frontend Y backend: fecha de evento solo en tipo `evento`; varios temas independientes; varios supermercados solo si se ha seleccionado un lugar y pertenecen a la red de ese lugar; al cambiar de lugar se descartan las antiguas selecciones incompatibles.
- **Contexto por cesta**: muestra las tiendas guardadas y qué cadenas tienen cobertura en la muestra de catálogos. Si faltan productos no presenta un total comparable ni promete ahorro.
- **Catálogo contextual**: filtra la muestra comercial por cadenas elegidas en la red del lugar. Los precios son **fichas web del 23/11/2026, no precio local, oferta vigente o stock**. No se atribuye la presencia de cada SKU a cada sucursal física.
- **Cestas compartidas**: se mantienen las invitaciones de un solo uso, roles lector/editor y el canal de actualizaciones entre dispositivos mientras la cesta está abierta.
- **Mi círculo**: peticiones de ayuda voluntaria visibles solo a amistades aceptadas. No hay personas vulnerables expuestas públicamente, ni geolocalización personal, ni asignación automática de servicios. El nombre de una cesta privada tampoco se revela a amistades sin permiso sobre esa cesta.
- **Despensa**: consulta rápida, avisos prudentes por productos parecidos ya registrados y registro de consumidos, sin afirmar una cantidad de desperdicio evitado no medida.
- **Conserva SHOPPER 10** en `/previous` y las herramientas de versiones anteriores en `/classic` (historial, SHOPPER Live, preferencias de shoppers, borradores, indicadores de coste). Todas comparten las mismas tablas.
- **Corrección GitHub/Docker**: `data/` ya no se excluye en bloque. El catálogo JSON público se empaqueta, pero se mantienen excluidas las bases de datos locales.

## Arranque local

Con Python 3.11 o posterior (versión probada: 3.13):

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python start.py
```

Abre `http://127.0.0.1:8000`. Para usarlo por Internet conserva **Railway + HTTPS + volumen persistente** y las variables privadas de las versiones anteriores.

### Configuración de producción

Ver `GUIA_ACTUALIZACION_RAILWAY_11.md`. **Nunca subas** SQLite, `.env`, códigos privados, capturas de usuarios ni datos personales a GitHub.

## API relevante

- `GET /health` → `version: 11.0`
- `GET /api/retail/catalog` → catálogo web de muestra **público, fechado**
- `GET /api/bootstrap` → datos privados autenticados y cestas con metadatos de portada
- `POST /api/baskets` y `PATCH /api/baskets/{id}` → `cover_emoji`, `accent`, `topics`, `place_id`, `preferred_store_ids`, `event_on`
- `GET /api/places/{id}/retail` → fichas web filtradas por cadenas que están en la red del lugar del usuario
- `GET /api/baskets/{id}/shopping-context` → tiendas y cobertura por cadena; no publica totales si hay incompletitud
- `GET/POST /api/circle/help` → solicitudes dentro del círculo de confianza
- `POST /api/circle/help/{id}/action` → `accept`, `done`, `cancel`

## Pruebas

```sh
pip install -r requirements-dev.txt
python -m pytest -q
node --check static/v11.js
```

**47 pruebas automatizadas** (nuevas y de regresión), entre ellas migración de base antigua, permisos cruzados, reglas condicionadas, filtrado por lugar y visibilidad de solicitudes entre amigos. Se ha examinado la maquetación en Chromium con una **vista previa de datos simulados** y probado en ella el selector dinámico; esto **no sustituye** probar el servidor real desde un iPhone físico.

## Fuentes, licencias, límites

- La muestra editorial de productos enlaza a catálogos web de **DIA** y **Carrefour** (fecha de captura especificada). No hay API comercial ni stock por sucursal.
- Open Food Facts se usa únicamente bajo configuración específica, con atribución y condiciones ODbL. No es inventario de supermercados.
- Los avisos SHOPPER Live son colaborativos y requieren corroboración; **no son hechos oficiales**.
- No se procesan compras, dinero ni remuneraciones de shoppers en esta beta.
- La ayuda entre amistades es voluntaria y no equivale a reparto profesional, servicio social ni ayuda de emergencia.

## Próxima validación comercial

1. Que cinco familias creen y **reutilicen** cestas durante dos semanas.
2. Comprobar productos concretos de dos tiendas y reportar cobertura fiable, no inventada.
3. Medir el tiempo necesario para preparar una compra y el porcentaje de listas reutilizadas.
4. Medir en qué casos una compra conjunta realmente reduce desplazamientos y costes, antes de automatizar rutas.
5. Valorar monetización solo cuando exista evidencia de que el servicio adicional cubre sus costes.
