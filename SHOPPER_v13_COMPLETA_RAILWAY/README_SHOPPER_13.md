# SHOPPER 13.0 — Mis tarjetas + Receta → Cesta

Nueva ampliación compatible con SHOPPER 12.0. La versión anterior sigue disponible en `/v12`; las APIs anteriores permanecen y la migración añade dos tablas sin sobrescribir cestas ni cuentas.

## Funcionalidades implementadas

**Tarjetas** (`/api/v13/cards`): una cartera por cuenta con códigos EAN-13, Code128 y QR estáticos, enlaces oficiales para tarjetas dinámicas, cifrado at-rest, listado enmascarado, representación visual bajo sesión y borrado. El uso de una tarjeta digital no garantiza que la tienda la acepte. No integra cuentas de fidelización de los supermercados ni activa ofertas.

**Recetas** (`/api/v13/recipes`): importador por texto o por JSON-LD Schema.org pegado; nombres, ingredientes, cantidades y raciones; recetario persistente y privado; comparador de referencias comerciales disponibles en la muestra por cadenas del lugar; paquetes completos, productos faltantes, sugerencias de alternativas limitadas y confirmación de sustitución; conversión a cesta editable. Ingredientes repetidos del mismo SKU se agregan antes de calcular paquetes para evitar compras duplicadas.

## Instalación local

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python start.py
```

En local, la ruta predeterminada es `http://127.0.0.1:8000`. Para pruebas sin datos privados, puedes habilitar las cuentas demo con `SHOPPER_DEMO=1`. No publiques un servidor con cuentas demo.

## Migración a Railway

Consulta [`GUIA_ACTUALIZACION_RAILWAY_13.md`](GUIA_ACTUALIZACION_RAILWAY_13.md). Realiza una copia de seguridad del volumen antes de desplegar. El servidor muestra `13.0` en `/health` tras instalar los nuevos archivos.

## Fiabilidad de la comparación

La muestra contiene referencias publicadas en webs oficiales de DIA y Carrefour, capturadas el **23 de noviembre de 2026**, sin garantía de vigencia ni inventario de ninguna tienda física. No se prometen descuentos ni ahorro real hasta obtener precio verificable en sucursal. Si no hay producto para un ingrediente, la cesta conserva una anotación manual pendiente y la comparación devuelve un subtotal incompleto, nunca un «precio total» falso. Las sugerencias de sustitución no certifican seguridad nutricional ni de alérgenos.

## Licencias y privacidad

Open Food Facts y Open Prices pueden ayudar a ampliar ingredientes y precios: sus APIs y datos están sujetos a ODbL, atribución y condiciones de reutilización. Los datos de marcas y catálogos de retailers no quedan automáticamente licenciados para redistribución por el simple hecho de estar publicados. Los códigos de fidelización requieren revisión de los términos de cada programa.

No hay acceso a cuentas de terceros, transacciones ni pedidos automáticos. Beta privada, no auditoría de seguridad formal. SQLite adecuada solo para primeras pruebas con una instancia; para escala conviene migrar a PostgreSQL y gestor de claves dedicado.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest -q
node --check static/v13.js
```
