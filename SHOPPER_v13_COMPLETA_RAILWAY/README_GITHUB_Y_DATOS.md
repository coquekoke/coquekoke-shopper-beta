# Archivos públicos y datos privados

Se incluye `data/retail_official_snapshot_2026-11-23.json` deliberadamente en Git y en la imagen Docker porque contiene una muestra comercial pública fechada.

**Nunca se debe subir** `*.sqlite3`, `.env`, credenciales, tokens, datos de clientes, adjuntos o archivos privados de soporte. La base de datos de producción se mantiene en el volumen de Railway.

Antes de cada despliegue: revisar `.gitignore`, `.dockerignore` y `git status` / los archivos de GitHub.
