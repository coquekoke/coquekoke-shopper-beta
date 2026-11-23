# SHOPPER 9.1 — Entrar desde un iPhone 15 (iOS 27)

**No tienes todavía una URL propia publicada: la crea Tailscale Serve cuando lo actives en tu ordenador.**

1. Descarga el ZIP de SHOPPER y descomprímelo en tu PC.
2. Instala Python 3.11+ y Tailscale. Inicia sesión en Tailscale del ordenador.
3. Abre `INICIAR_PRIVADO_IPHONE_WINDOWS.bat`. Conserva esa ventana abierta y guarda el código privado que muestra.
4. En otra ventana de PowerShell ejecuta:
   ```powershell
   tailscale serve --bg 8000
   tailscale serve status
   ```
5. Instala Tailscale en tu iPhone, inicia sesión y actívalo.
6. Abre Safari y pega la URL completa `https://...ts.net` que te ha mostrado Tailscale. Crea una cuenta con el código privado, usuario y contraseña propia de 12+ caracteres.
7. En Safari → Compartir → Añadir a pantalla de inicio → **Abrir como app web** (si aparece). Ya puedes abrir SHOPPER con su propio icono.
8. En el móvil del familiar, instala Tailscale y autoriza acceso al servidor con una invitación de Tailscale. Esa persona crea una cuenta SHOPPER distinta; invítala después a una cesta desde «Mis cestas».
9. Comprobad que la persona A añade leche y que la persona B lo ve y marca como comprada. Probad también «Mi círculo» → crear y aceptar un recado.

**Si falla:** servidor Python encendido, Tailscale conectado en ambos, URL HTTPS correcta, `tailscale serve status`, permisos familiares en Tailscale. No uses `tailscale funnel`: eso haría el sitio accesible públicamente.

Este procedimiento no exige pagar por App Store ni subir la app a Apple; es una **web app privada**. No funcionará sin conexión al servidor.

**Si ya utilizabas SHOPPER 7 u 8:** antes de iniciar el servidor privado, sigue los pasos de migración del README. Se crearán nuevas contraseñas provisionales; no reutilices las contraseñas antiguas.
