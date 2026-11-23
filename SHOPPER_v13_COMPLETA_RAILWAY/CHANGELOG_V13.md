# SHOPPER 13.0 · 2026-11-23

- Cartera privada cifrada por usuario, representaciones EAN-13/Code128/QR y vínculos a programas oficiales.
- Importador de ingredientes desde texto y JSON-LD `Recipe` pegado.
- Conversión de cantidades, paquetes completos y agregación de ingredientes repetidos.
- Comparación por cadena y por red de tiendas del lugar; totales solo cuando hay cobertura completa de la muestra.
- Alternativas de productos próximas con confirmación expresa y exclusión de sustituciones inseguras para dietas indicadas.
- Conversión de recetas a cestas ocasionales editables; faltantes como anotaciones manuales.
- Cambios acumulativos: nuevas tablas SQLite `v13_*`, endpoints `/api/v13/*`, interfaz `/static/v13.*`.
- `/v12` conserva la interfaz previa. Se preservan datos y permisos anteriores.
- Nueva documentación de despliegue seguro, fuentes y límites.
