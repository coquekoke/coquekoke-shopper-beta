# SHOPPER Madrid · fuentes legales, escala y propuesta de valor

## Una verdad operativa que condiciona todo

No existe una API pública gratuita universal que proporcione por sucursal **todas las referencias, precios promocionales, descuentos personalizados, stock, fechas de caducidad y capacidad de preparación de pedidos** de Mercadona, DIA, Carrefour, Lidl, Alcampo, Ahorramás, etc. Para cumplir la ley y no engañar, el sistema distingue: `punto de venta`, `referencia comercial`, `anuncio de cadena`, `observación en tienda`, `precio con evidencia`, `stock integrado oficialmente` (aún no disponible) y `pedido aceptado oficialmente` (aún no disponible).

| Fuente | Qué sí se podría integrar | Restricciones / coste / madurez |
|---|---|---|
| OpenStreetMap y extractos Geofabrik | Tiendas y sus coordenadas, direcciones y marcas cuando consten | ODbL (atribución + obligaciones share-alike), calidad desigual. Descarga/importe por lotes, no sobrecargar API pública Overpass; tiendas no necesariamente abiertas |
| Ayuntamiento de Madrid, censo de locales/actividades | Registros administrativos de actividad y local, municipio de Madrid | CC BY 4.0 con atribución, reconciliar dirección+actividad+estado; no es censo completo de Comunidad de Madrid ni catálogo de precios |
| Open Food Facts | GTIN, nombres, marcas, etiquetas, información nutricional, alérgenos cuando consten | ODbL / atribución / share-alike, cobertura y exactitud desiguales, límites API, imágenes con licencias específicas. No stock ni precios por tienda |
| Open Prices | Precios comunitarios asociados a producto, lugar y evidencias | ODbL y atribución/compatibilidad de base; observaciones con fecha, no son stock ni ofertas en tiempo real |
| Catálogos oficiales de cadena | Productos concretos observables, formatos y precios web | Publicación online NO es licencia masiva de copia/reventa. Solicitar permiso/feeds o utilizar ejemplos editoriales limitados y enlazados, de forma compatible con derecho aplicable |
| API de plataformas de comparación | Listados, índices, históricos | Licencia contractual expresa, condiciones de redistribución, tarifas, caché/limites. Algunas APIs abiertas prohíben usos comerciales; nunca eludir autenticación ni controles |
| Tiendas adheridas (futuro) | Feed autorizado de surtido local, promociones, inventario, preparación y recogida | Integración negociada, contrato, seguridad, disponibilidad y SLA; única vía para prometer stock y preparación fiables |

## Arquitectura sostenible para crecer

1. **PostgreSQL/PostGIS** en producción al superar el piloto: entidades `brands`, `groups`, `products/GTIN`, `chains`, `stores`, `user_places`, `basket_collections`, `store_price_evidence`, `offers`, `stock_evidence`, `orders`, `pantry_movements`, `community_reports`, `user_permissions`.
2. **Ingesta separada por licencia/propiedad y procedencia**: OSM ODbL en esquema apropiado con atribución; catálogos comerciales licenciados en tablas de distribución acorde al contrato; evidencias de tickets/observaciones en tablas propias y permisos de privacidad.
3. **Observación con vida útil**: precio, fecha, sucursal, fuente, exactitud y caducidad; no convertir un único ticket de ayer en una promoción actual garantizada.
4. **Search**: producto exacto por EAN, equivalencia por formato/unidad y dieta/alérgenos comprobados, texto libre y filtros de cadenas múltiples con conjuntos de tiendas por ubicación.
5. **Optimización con restricciones**: coste de los productos comparables, cobertura, promociones compatibles, distancia/ruta, logística, cadena de frío, remuneración y riesgo de desabastecimiento. Si faltan precios, informar porcentaje de cobertura, no inventar ahorro.
6. **Geografía**: carga inicial masiva por extracto local/GeoJSON bajo licencia + actualizaciones incrementales en backend. Geolocalización opt-in; casa/abuelos solo visible al dueño/autorizados.
7. **Escala social**: moderación, denuncia, antispam, caducidad de avisos, reputación basada en evidencias, restricciones de edad y privacidad antes de abrir la red públicamente.
8. **Pedidos**: integrar servicios de preparación oficiales solo al contar con acuerdos; pagos mediante proveedor regulado y control de identidad/remuneración/seguros si se presta logística propia.

## USP propuesto: SHOPPER Cesta Viva

> Tu biblioteca de compras, las tiendas de tus lugares y tu círculo cercano, en una única herramienta que aprende qué compras y evita repetir trabajo y desplazamientos.

Flujos diferenciales a validar con hogares reales:

- **Mis mixtapes de compra**: cestas permanentes estilo Spotify («Mi semana», «Cena de 8», «Aperitivo», «Para los abuelos»), reutilizables y compartibles, con acceso rápido a variantes sin volver a configurar todo.
- **Mi atlas familiar**: lugares personales (Casa, Trabajo, Padre, Pueblo) cada uno con varias tiendas de referencia; búsqueda de catálogos y fuentes fechadas de esas cadenas, sin fingir stock local.
- **Yo paso por ahí**: aviso voluntario entre contactos aceptados para compartir un recado compatible con la ruta, no exposición pública de hogares vulnerables. Productos perecederos requieren seguridad alimentaria; no realizar reventa informal ni cobrar servicios sin encuadramiento legal.
- **Cierre de bucle**: registrar compra real (cesta + extras), confirmar entrega y transferir a despensa opcional; en la próxima compra advertir posibles duplicados antes de comprar de más.
- **Waze del lineal**: observaciones recientes de cambios, agotados, precios y nuevos productos con fecha y corroboración. No atribuir veracidad oficial a aportaciones.

## Lo que debe demostrar rentabilidad

Métricas de primer piloto (10–20 hogares): retención semanal de las cestas; porcentaje de compras creadas mediante colección ya guardada; segundos para preparar lista; compras duplicadas advertidas y confirmadas por usuarios; proporción de referencias con precio fechado y comparabilidad completa; avisos válidos, corroboraciones y falsos positivos; frecuencia de ayudas completas entre conocidos; disposición a pagar por compras asistidas, coste de cada ruta y contribución por encargo.

**Secuencia:** primero información fiable y recurrencia; segundo familias/amigos y productividad; tercero acuerdos con tiendas locales; cuarto compra asistida legal y pagos; por último publicidad patrocinada indicada y B2B con derechos de datos. 

## Enlaces originales de referencia

- Censo municipal: https://datos.madrid.es/dataset/200085-0-censo-locales
- OpenStreetMap licencia: https://www.openstreetmap.org/copyright
- Geofabrik: https://download.geofabrik.de/europe/spain.html
- Open Food Facts: https://openfoodfacts.github.io/openfoodfacts-server/api/
- Open Prices: https://prices.openfoodfacts.org/
- Overpass: https://wiki.openstreetmap.org/wiki/Overpass_API
- MapLibre: https://maplibre.org/

Confirmar condiciones y permisos en la fecha de puesta en producción; licencia abierta no es «sin copyright» ni significa ausencia de obligaciones.
