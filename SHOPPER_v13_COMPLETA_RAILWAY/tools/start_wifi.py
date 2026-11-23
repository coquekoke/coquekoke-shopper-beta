"""Optional trusted home Wi-Fi test; do NOT port-forward or publish HTTP endpoint."""
from pathlib import Path
import json, os, secrets, socket, subprocess, sys, stat
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'.shopper_private.json'
if FILE.exists():
    data=json.loads(FILE.read_text(encoding='utf-8'))
else:
    data={'csrf_key':secrets.token_urlsafe(48),'signup_code':secrets.token_urlsafe(26)}
    FILE.write_text(json.dumps(data,indent=2),encoding='utf-8')
    try: FILE.chmod(stat.S_IRUSR|stat.S_IWUSR)
    except OSError: pass
if len(data.get('csrf_key',''))<32 or len(data.get('signup_code',''))<16:
    raise SystemExit('Los secretos locales no son válidos. Aborta.');

def local_ipv4():
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1',80))
            return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'

ip=local_ipv4()
(ROOT/'data').mkdir(exist_ok=True)
env=os.environ.copy()
env.update(SHOPPER_DB=str(ROOT/'data'/'shopper.sqlite3'),SHOPPER_LAN='1',SHOPPER_REMOTE='0',SHOPPER_DEMO='0',SHOPPER_CSRF_KEY=data['csrf_key'],SHOPPER_SIGNUP_CODE=data['signup_code'],SHOPPER_ALLOWED_HOSTS=ip)
print('SHOPPER 9.2 · SOLO PARA PRUEBAS EN WI-FI DE CONFIANZA')
print('iPhone en la misma Wi-Fi: http://'+ip+':8000')
print('PC: http://localhost:8000')
print('Codigo de registro privado: '+data['signup_code'])
print('IMPORTANTE: esta prueba usa HTTP sin cifrar; no uses datos personales ni contrasenas reutilizadas.')
print('No abras puertos del router ni uses este modo a traves de un tunel publico.')
raise SystemExit(subprocess.call([sys.executable,'-m','uvicorn','main:app','--host','0.0.0.0','--port','8000','--workers','1'],cwd=str(ROOT),env=env))
