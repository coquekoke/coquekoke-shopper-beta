#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo 'SHOPPER 8.0 — ALFA LOCAL · solo 127.0.0.1'
command -v python3 >/dev/null || { echo 'Necesitas instalar Python 3.11+'; exit 1; }
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export SHOPPER_DEMO=1
echo 'Abre http://127.0.0.1:8000 · Detener: Ctrl+C'
exec .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
