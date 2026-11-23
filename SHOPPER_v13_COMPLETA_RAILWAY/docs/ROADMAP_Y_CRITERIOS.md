# SHOPPER 8.0 — De alfa a negocio con resultados medibles

## Principio rector

Una única cuenta / tres experiencias: **Comprar**, **Explorar y colaborar**, **Solicitar ser shopper**. Un catálogo de productos y establecimientos compartido en el servidor y privacidad por usuario para cestas, lugares y despensa.

No se cobra una micro-suscripción de 0,10 €. Las funciones de comparar, crear cestas, aprender sobre marcas y reportar cambios siguen como propuesta de base gratuita. Los ingresos iniciales **hipotéticos** vendrían de una tarifa por encargo, solo cuando el servicio esté regulado y viable, con alternativas B2B (preparación autorizada/excedentes/servicios a retailers) explorables después.

## Hipótesis y experimentos que deben falsarse

| Hipótesis | Cómo probarla | Umbral exploratorio (NO pronóstico) |
|---|---|---|
| La gente vuelve a organizar cestas | 10–15 hogares durante 4 semanas | ≥ 6 hogares vuelven 3 semanas distintas |
| El catálogo es útil sin inventar información | 20–50 SKUs verificados físicamente con ticket/foto propia | ≥ 80 % de identificación correcta y precios etiquetados con fuente |
| Despensa evita compras repetidas | Opt-in y diario de compra antes/después | N.º de compras duplicadas evitadas reportadas y validadas |
| La información comunitaria merece atención | Avisos de un solo supermercado + moderación manual | Tiempo hasta corrección, falsos positivos, reportes útiles |
| Se puede prestar un encargo sin perder dinero | 5–10 simulaciones/manuales legales y consentidas | Contribución positiva por servicio completo, incluyendo incidencias |
| La cesta familiar ayuda a mayores y personas ocupadas | 3 familias con permiso explícito | Tareas finalizadas y minutos ahorrados autodeclarados |

## Métricas reales vs alegaciones

- **Ahorro monetario** = coste de referencia comparable de una cesta con idénticos SKU/formato/condiciones menos coste real de compra y servicio. Si falta cobertura, mostrar incompleto; no extrapolar a productos ausentes.
- **Ahorro de tiempo** = encuesta/diario del hogar sobre tarea y ruta equivalente, con intervalos y sin asegurar causalidad.
- **Desperdicio** = kg/unidades de producto descartado que la persona registra, por periodo, con tasa de registro; no afirmar «kg evitados» por defecto.
- **Emisiones** = no atribuir CO₂ evitado sin comparar recorridos y factores de emisión adecuados. Agrupar pedidos puede reducir o aumentar emisiones según el caso.
- **Contribución** = tarifa sin IVA − trabajador/tiempo de tienda − desplazamientos − pagos − soporte − cancelaciones esperadas; no confundir con beneficio neto empresarial.

## Hoja de ruta por puertas de calidad

### Gate 0 — Alfa ejecutable local (estado: construida, NO validada en mercado)

- Cuentas locales, cestas compartidas por invitación, catálogo pequeño, dos tiendas de ejemplo, despensa, avisos, comparación prudente y borradores.
- 24 pruebas automatizadas de API y migración a fecha de esta versión; deben ejecutarse tras cada cambio.
- Nunca reclamar que hay stock real, descuentos oficiales o encargos confirmados.

### Gate 1 — Prueba privada personal con socios voluntarios

- Seleccionar una zona pequeña: Ciudalcampo / Santo Domingo / Madrid norte como entorno de referencia, sin asumir cobertura de todo Madrid.
- Introducir 20–50 referencias y precios *verificados*, fechados y con fuente. Sin levantar masivamente bases protegidas de supermercados.
- 10–15 hogares y 2 tiendas como máximo al principio. Información de precios obtenida respetando condiciones de terceros.
- Revisar la accesibilidad, compatibilidad móvil, problemas de cámara/barcodes, duplicados y tiempos de tarea.
- Registrar solicitudes de funciones y errores en el propio panel de feedback.

### Gate 2 — Beta de varias personas a distancia

- Reemplazar SQLite local por **PostgreSQL**, migraciones versionadas y copia de seguridad automática.
- Autenticación con correo verificado, recuperación de contraseña, sesiones seguras y control de acceso auditado.
- API con límites contra spam, reportes dañinos, moderación humana, trazabilidad, revisión y apelaciones, retención adecuada.
- RGPD/LOPDGDD y transparencia para datos de familiares, domiciliarios, geolocalización, fotografías y relaciones sociales.
- Infraestructura HTTPS, registros de operación sin datos personales innecesarios, despliegue de staging y pruebas de recuperación.
- Conector(es) de datos bajo licencia o acuerdo; catálogo y tienda físicos distinguidos; precio fuente/antigüedad/condiciones.

### Gate 3 — Piloto comercial de compras

- Revisar el modelo jurídico de relación con shopper (Ley 12/2021 y Directiva (UE) 2024/2831), seguros, higiene/cadena de frío, pagos y responsabilidad frente al consumidor.
- Selección y activación manual de 1–2 trabajadores correctamente encuadrados, tras comprobar documentación legal aplicable.
- Limitar rutas y no aceptar operaciones que tengan coste variable superior a la tarifa acordada.
- Pickup por shopper: punto exterior permitido, franja de recepción, confirmación y política de ausencias revisada jurídicamente.
- Preparación por tienda únicamente si un comercio firma un acuerdo y la integración de pedidos funciona.

### Gate 4 — Escalado selectivo

- Automatizar grupos de supermercados por lugares, optimización de ruta real, predicción de disponibilidad calibrada, alertas autorizadas, seguimiento de eventos, comercios colaboradores y excedentes alimentarios.
- Iniciar publicación en App Store y Play Store solo después de validar privacidad, pagos, seguridad y experiencia móvil; la PWA puede preceder a apps nativas.
- Analítica de costos del fundador, CAC, retención, tasa de incidencias, utilidad social y margen de contribución antes de expandir barrios.

## Arquitectura y propiedad tecnológica

**Ahora:** FastAPI + SQLite + archivos frontend; API REST local, pruebas API, no dependencia de proveedor externo para arrancar. **Después:** PostgreSQL/PostGIS, colas/background workers, object storage, procesamiento de imágenes, telemetry y herramientas de observabilidad. **Móvil:** PWA como etapa, Expo/React Native si la investigación del producto lo justifica.

Desarrollo: GitHub como repositorio central bajo control del fundador, Cursor o VS Code para edición y debugging, ChatGPT para estrategia, especificación y test plans. No usar varios generadores para reemplazar el repositorio entre cada iteración.

Registro de marca: búsqueda previa de SHOPPER y variantes en OEPM y EUIPO, clases apropiadas con profesional, y dominio disponible; no confundir nombre de proyecto con marca concedida.

## Riesgos y mitigación prioritaria

1. **Datos de supermercados:** un directorio de tiendas no da acceso al catálogo ni inventario. OSM bajo ODbL requiere atribución y respeto de licencia; Open Food Facts ODbL requiere cumplir los términos al reutilizar su base.
2. **Avisos incorrectos o difamatorios:** no tratar comentarios como hechos oficiales; caducidad, corroboración y moderación, y separación de alertas oficiales alimentarias.
3. **Despensa y nutrición:** fechas y cantidades introducidas por el usuario, no certificación sanitaria; nutrición con fuente y advertencia de alérgenos.
4. **Privacidad de familiares y menores:** no revelar direcciones/ubicación a miembros de una cesta por defecto; controles de permisos por recurso.
5. **Operativa de compra:** alimentos refrigerados, no-presentaciones, sustituciones consentidas, confirmación de entrega y responsabilidades.
6. **Económico:** precio de tarifa > costes variables no implica beneficio neto; atención al cliente, seguros, impuestos, adquisición y estacionalidad pueden absorber márgenes.

## Investigación a consultar

- [Open Food Facts y licencias](https://world.openfoodfacts.org/data)
- [OpenStreetMap y ODbL](https://www.openstreetmap.org/copyright)
- [OEPM](https://www.oepm.es/)
- [EUIPO](https://www.euipo.europa.eu/)
- [AESAN](https://www.aesan.gob.es/)
- [BOE](https://www.boe.es/)
