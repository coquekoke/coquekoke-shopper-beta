# Auditoría de continuidad SHOPPER 7 → 8 → 9.1

## Comprobación de versiones

| Paquete | Pruebas locales de API/regresión antes del cierre | Resultado |
| --- | ---: | --- |
| SHOPPER 7 | 15 | Correctas |
| SHOPPER 8 | 24 | Correctas |
| SHOPPER 9 | 28 | Correctas |
| SHOPPER 9.1 | 30 | Correctas |

Este documento registra pruebas efectuadas en el entorno de desarrollo. No equivale a una auditoría externa ni a una validación en iPhone físico.

## Las tareas que quedaron completas en V8

- Carta comunitaria por sucursal y precio aportado, sin equivaler a inventario conectado.
- Productos seguidos: avisos basados en observaciones posteriores a la suscripción, sin notificaciones push.
- Copiar cestas recurrentes o compartidas a la cesta Actual.
- Consumo parcial y descarte parcial en despensa, con historial.
- Compras declaradas con total, duración y snapshot inmutable.
- Sincronización mediante sondeo; V9 incorpora canal SSE y sondeo de respaldo.
- Consulta opcional Open Food Facts, con controles de acceso y límites.
- Cobertura de tests V7 preservada; paquetes revisados sin datos personales.

## Deficiencias encontradas al revisar

1. V9 no disponía de ruta lista para migrar un uso previo real de V7/V8 al nuevo `data/shopper.sqlite3` con credenciales adecuadas. Resuelto en 9.1 mediante migración offline sin sobrescritura y rotación de contraseñas.
2. La herramienta de backup heredada buscaba por defecto la base antigua en la raíz y no la que utiliza `tools/start_private.py`. Corregido en 9.1.

## Lo que sigue sin estar completo (de manera consciente)

- SHOPPER no está publicado en la nube, App Store ni Play Store; el usuario debe configurar Tailscale y mantener un servidor privado.
- No hay stock oficial, carta completa, precios garantizados ni preparación de pedidos por DIA, Sánchez Romero u otras cadenas.
- No hay pagos, verificación de shoppers, contratos operativos, seguros ni logística de pedidos reales.
- No hay verificación de correo, recuperación automática de contraseña, auditoría de seguridad externa ni almacenamiento cloud con alta disponibilidad.
- No hay pruebas en un iPhone físico ni pruebas de campo con familiares, ni evidencia de ahorro neto o reducción real de desperdicio.
- La comunidad necesita moderación, controles antifraude y política de privacidad antes de abrirse a desconocidos.
- Si existen datos nuevos en dos bases distintas (V8 y V9), NO hay fusión automática; requiere conciliación específica.

## Reglas de entrega

Nunca sobrescribir una base de datos existente sin respaldo y verificación. No empaquetar credenciales, secretos ni bases privadas. Mantener las operaciones comerciales bloqueadas hasta contar con sistemas y autorizaciones reales.
