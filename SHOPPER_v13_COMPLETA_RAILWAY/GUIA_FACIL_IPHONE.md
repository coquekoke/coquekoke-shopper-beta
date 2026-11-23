# SHOPPER en iPhone sin Tailscale: decide en dos minutos

## Opción A · Casa, mismo Wi-Fi (la más rápida para probar)

1. Descomprime el ZIP, instala Python 3.11+, ejecuta `INICIAR_WIFI_CASA_WINDOWS.bat`.
2. El PC muestra una dirección como `http://192.168.1.45:8000` y un código privado de alta. **No uses literalmente ese ejemplo:** copia la IP que muestre tu ordenador.
3. Conecta el iPhone a la misma Wi-Fi y abre esa URL en Safari. Regístrate con usuario y contraseña **de prueba** de 12+ caracteres y el código.
4. Crea una cesta. Desde un segundo navegador u otro iPhone en esa misma Wi-Fi, crea otra cuenta y comparte la cesta mediante invitación.
5. Si no carga: comprueba que el PC sigue encendido, los dos están en la misma Wi-Fi, que la IP no es 127.0.0.1, y permite el acceso a Python solo en redes privadas mediante Firewall de Windows. Algunos routers aíslan los dispositivos de Wi-Fi invitados; evita esa red.

**Advertencia: este modo usa HTTP sin cifrar**, por lo que no es para contraseñas reales/reutilizadas ni información personal. No configures redirección de puertos del router, no lo publiques mediante ngrok y no lo uses fuera de una red de confianza. En iOS ciertas APIs PWA requieren HTTPS.

## Opción B · Fuera de casa, acceso familiar sin PC (recomendada)

Sigue `GUIA_RAILWAY.md`. El servidor vive en Railway con HTTPS y un volumen para conservar las cestas. La configuración es una vez; tu familiar solo abre una URL y crea una cuenta con un código de alta privado.

## iPhone: añadir como aplicación

En Safari con SHOPPER abierta por su **URL HTTPS**: Compartir → Añadir a pantalla de inicio → Abrir como app web (si aparece) → Añadir. El icono no convierte la PWA en una app publicada en App Store.

## Comparación breve

- Wi-Fi local: gratuita, PC encendido, HTTP sin cifrar, mismo Wi-Fi.
- ngrok: accesible desde cualquier sitio, pero el PC sigue encendido y el túnel necesita protección de acceso, no recomendable con la beta sin auditoría.
- Tailscale Serve: HTTPS privado y familiar autorizado, pero todos requieren acceso a la red Tailscale.
- Railway: HTTPS desde cualquier lugar sin PC encendido; coste/consumo y configuración inicial, beta en una URL pública protegida por autenticación.
- Render gratuito: **NO** para la SQLite actual, porque el disco gratuito es efímero.
