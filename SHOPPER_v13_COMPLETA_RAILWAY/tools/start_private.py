"""SHOPPER: start one private server behind Tailscale Serve (HTTPS termination).
The server listens on localhost, not an exposed network interface.
"""
import json, os, secrets, stat, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SECRET_FILE=ROOT/'.shopper_private.json'
if SECRET_FILE.exists():
    data=json.loads(SECRET_FILE.read_text(encoding='utf-8'))
else:
    data={'csrf_key':secrets.token_urlsafe(48),
          'signup_code':secrets.token_urlsafe(26)}
    SECRET_FILE.write_text(json.dumps(data,indent=2),encoding='utf-8')
    try:SECRET_FILE.chmod(stat.S_IRUSR|stat.S_IWUSR)
    except OSError:pass
    print('NUEVA CONFIGURACIÓN PRIVADA. Nunca subas este archivo a GitHub.')
if len(data.get('csrf_key',''))<32 or len(data.get('signup_code',''))<16:
    sys.exit('Configuración privada inválida. Revisa .shopper_private.json.')
folder=ROOT/'data';folder.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
env.update(SHOPPER_DB=str(folder/'shopper.sqlite3'),SHOPPER_REMOTE='1',SHOPPER_DEMO='0',
           SHOPPER_CSRF_KEY=data['csrf_key'],SHOPPER_SIGNUP_CODE=data['signup_code'])
print('\nSHOPPER 9.1 — MODO FAMILIAR PRIVADO')
print('En otra terminal configura Tailscale Serve:')
print('    tailscale serve --bg 8000')
print('    tailscale serve status')
print('Abre desde iPhone la URL HTTPS *.ts.net mostrada por Tailscale; NO uses Funnel.')
print('CODIGO PRIVADO PARA CREAR CUENTAS (comunica solo a familiares):')
print('    '+data['signup_code'])
print('El ordenador ha de permanecer encendido. Ctrl+C detiene la app.\n')
raise SystemExit(subprocess.call([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8000','--workers','1'],cwd=str(ROOT),env=env))
