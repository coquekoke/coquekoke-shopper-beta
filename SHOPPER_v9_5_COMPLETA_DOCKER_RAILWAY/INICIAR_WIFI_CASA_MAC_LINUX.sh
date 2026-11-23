#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
.venv/bin/python tools/start_wifi.py
