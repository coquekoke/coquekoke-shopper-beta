"""SHOPPER 9.2 | private cross-device family beta.

Single-instance deployment; no actual supermarket, payments or gig bookings.
Use HTTPS/Tailscale and explicit signup codes; security review required for wider launch.
"""
from __future__ import annotations
import asyncio, csv, hashlib, hmac, io, itertools, json, os, re, secrets, sqlite3, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from math import asin, cos, radians, sin, sqrt
from collections import deque
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from db import ROOT, connect, init, many, one, now, pbkdf2, token_hash

REMOTE=os.getenv('SHOPPER_REMOTE','0')=='1'
LAN_PRIVATE=os.getenv('SHOPPER_LAN','0')=='1'
PRIVATE_MODE=REMOTE or LAN_PRIVATE
if REMOTE and LAN_PRIVATE: raise RuntimeError('Selecciona solo uno de SHOPPER_REMOTE o SHOPPER_LAN')
if os.getenv('RAILWAY_ENVIRONMENT_NAME') and not REMOTE:
    raise RuntimeError('En Railway SHOPPER_REMOTE=1 es obligatorio; nunca despliegues el modo local por Internet.')
if os.getenv('RAILWAY_ENVIRONMENT_NAME') and os.getenv('SHOPPER_REQUIRE_VOLUME')!='1':
    raise RuntimeError('En Railway SHOPPER_REQUIRE_VOLUME=1 es obligatorio para proteger la base SQLite.')
COOKIE_NAME='shopper_session'
CSRF_KEY=os.getenv('SHOPPER_CSRF_KEY','shopper-local-dev-secret-do-not-use-on-internet')
SIGNUP_CODE=os.getenv('SHOPPER_SIGNUP_CODE','')
if PRIVATE_MODE:
    if len(CSRF_KEY)<32 or len(SIGNUP_CODE)<16:
        raise RuntimeError('Modo remoto: configura SHOPPER_CSRF_KEY (32+ chars) y SHOPPER_SIGNUP_CODE (16+ chars)')
    if os.getenv('SHOPPER_DEMO','0')=='1':
        raise RuntimeError('No habilites cuentas demo en modo privado')
if os.getenv('SHOPPER_REQUIRE_VOLUME','0')=='1':
    from db import DB_PATH
    _volume=os.getenv('RAILWAY_VOLUME_MOUNT_PATH','')
    _db=DB_PATH.resolve()
    if not _volume or not Path(_volume).is_absolute():
        raise RuntimeError('Falta un volumen persistente Railway: asocia un volumen al servicio antes de iniciar.')
    _root=Path(_volume).resolve()
    if not _db.is_relative_to(_root):
        raise RuntimeError('SHOPPER_DB debe estar dentro de RAILWAY_VOLUME_MOUNT_PATH para conservar cestas.')
    if not os.path.ismount(_root):
        raise RuntimeError('El directorio del volumen no está montado: deteniendo para impedir perder datos.')
init()
app = FastAPI(title='SHOPPER 13 | recetas y tarjetas',version='13.0',docs_url=None if PRIVATE_MODE else '/docs',redoc_url=None)
hosts=['localhost','127.0.0.1','testserver','*.ts.net','*.up.railway.app','*.onrender.com']
hosts += [x.strip() for x in os.getenv('SHOPPER_ALLOWED_HOSTS','').split(',') if x.strip()]
app.add_middleware(TrustedHostMiddleware,allowed_hosts=hosts)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

def csrf_for(token:str)->str:
    return hmac.new(CSRF_KEY.encode(),token.encode(),hashlib.sha256).hexdigest()

# Lightweight login throttle (one worker only). Complement with network access controls.
_attempts={}
_attempt_lock=Lock()
def login_limit(address:str,username:str,failed:bool):
    key=(address,username.strip().lower()[:100])
    clock=time.monotonic()
    with _attempt_lock:
        active=[t for t in _attempts.get(key,[]) if clock-t<600]
        if not failed and len(active)>=6:
            raise HTTPException(429,'Demasiados intentos. Prueba de nuevo más tarde.')
        if failed:active.append(clock)
        else:active=[]
        if active:_attempts[key]=active
        else:_attempts.pop(key,None)

def set_auth_cookie(response:Response,token:str):
    response.set_cookie(COOKIE_NAME,token,max_age=7*86400,httponly=True,secure=REMOTE,
                        samesite='strict',path='/')

@app.middleware('http')
async def safety_headers(req:Request,call_next):
    if PRIVATE_MODE and req.url.path.startswith('/api/') and req.method not in ('GET','HEAD','OPTIONS'):
        origin=req.headers.get('origin')
        referer=req.headers.get('referer')
        candidate=origin or (f'{urlparse(referer).scheme}://{urlparse(referer).netloc}' if referer else '')
        expected=('https://' if REMOTE else 'http://')+req.headers.get('host','')
        if candidate!=expected:
            return JSONResponse({'detail':'Origen no autorizado (HTTPS obligatorio)'},status_code=403)
        if req.url.path not in ('/api/auth/login','/api/auth/register'):
            session=req.cookies.get(COOKIE_NAME,'')
            csrf=req.headers.get('x-shopper-csrf','')
            if not session or not hmac.compare_digest(csrf,csrf_for(session)):
                return JSONResponse({'detail':'Validación de sesión necesaria'},status_code=403)
    if req.method in ('POST','PUT','PATCH') and req.url.path.startswith('/api/'):
        try:
            if int(req.headers.get('content-length','0'))>65536:
                return JSONResponse({'detail':'Solicitud demasiado grande'},status_code=413)
        except ValueError:
            return JSONResponse({'detail':'Longitud de solicitud incorrecta'},status_code=400)
    response=await call_next(req)
    response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
       'X-Frame-Options':'DENY','Cache-Control':'no-store' if req.url.path.startswith('/api') else 'no-cache',
       'Permissions-Policy':'camera=(self), geolocation=(self)',
       'Content-Security-Policy':"default-src 'self'; img-src 'self' data: blob: https://images.openfoodfacts.org https://static.openfoodfacts.org https://*.openfreemap.org; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self' https://tiles.openfreemap.org https://*.openfreemap.org; worker-src blob:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
    if REMOTE:response.headers['Strict-Transport-Security']='max-age=15552000'
    return response

@app.get('/health')
def health():return {'ok':True,'app':'SHOPPER','version':'13.0','mode':'cloud' if REMOTE else ('wifi-local' if LAN_PRIVATE else 'local')}

@app.get('/api/config')
def public_config():return {'remote':REMOTE,'signup_code_required':PRIVATE_MODE,'demo_mode':not PRIVATE_MODE and os.getenv('SHOPPER_DEMO','0')=='1','version':'13.0'}

@app.get('/')
def home(): return FileResponse(ROOT/'static'/'v13.html')

@app.get('/v12')
def v12():return FileResponse(ROOT/'static'/'v12.html')

@app.get('/previous')
def previous():return FileResponse(ROOT/'static'/'v11.html')

@app.get('/v10')
def v10():return FileResponse(ROOT/'static'/'v10.html')

@app.get('/v11')
def v11():return FileResponse(ROOT/'static'/'v11.html')

@app.get('/classic')
def classic(): return FileResponse(ROOT/'static'/'index.html')

bearer=HTTPBearer(auto_error=False)

def session_token(req:Request,c:HTTPAuthorizationCredentials|None):
    if not PRIVATE_MODE and c is not None and c.scheme.lower()=='bearer':return c.credentials
    if req.cookies.get(COOKIE_NAME):return req.cookies[COOKIE_NAME]
    return ''

def auth(req:Request,c: HTTPAuthorizationCredentials|None=Depends(bearer)):
    token=session_token(req,c)
    if not token:raise HTTPException(401,'Inicia sesión para continuar')
    with connect() as db:
        u=one(db,'''SELECT u.id,u.username,u.display_name,u.friend_code FROM sessions s JOIN users u ON u.id=s.user_id
             WHERE s.token_digest=? AND s.expires_at>?''',(token_hash(token),now()))
    if not u:raise HTTPException(401,'Sesión caducada o no válida')
    return u

def existing(db,table, ident):
    record=one(db,f'SELECT * FROM {table} WHERE id=?',(ident,))
    if not record:raise HTTPException(404,f'{table}: registro no encontrado')
    return record

def own_place(db,id,user_id):
    p=one(db,'SELECT * FROM places WHERE id=? AND user_id=?',(id,user_id))
    if not p:raise HTTPException(403,'Este lugar no pertenece a tu cuenta')
    return p

def basket_access(db,bid,uid,write=False,owner=False):
    b=existing(db,'baskets',bid)
    if b['owner_id']==uid:return b
    if owner:raise HTTPException(403,'Solo el propietario puede hacer esto')
    role=one(db,'SELECT role FROM basket_members WHERE basket_id=? AND user_id=?',(bid,uid))
    if not role or (write and role['role']!='editor'):raise HTTPException(403,'No tienes permiso para esta cesta')
    return b

def require_local_value(v,maxlen=120):
    return v.strip()[:maxlen]

class Register(BaseModel):
    username:str=Field(min_length=3,max_length=24,pattern=r'^[a-zA-Z0-9._-]+$')
    display_name:str=Field(min_length=2,max_length=60)
    password:str=Field(min_length=12,max_length=128)
    signup_code:str|None=None

class Login(BaseModel):
    username:str
    password:str

def issue_token(db,uid):
    token=secrets.token_urlsafe(40)
    db.execute('INSERT INTO sessions VALUES (?,?,?,?)',
       (token_hash(token),uid,now(),(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(timespec='seconds')))
    return token

@app.post('/api/auth/register')
def register(d:Register,response:Response):
    if PRIVATE_MODE and not hmac.compare_digest(d.signup_code or '',SIGNUP_CODE):
        raise HTTPException(403,'Código privado incorrecto o no recibido. Revisa el valor activo en Railway (SHOPPER_SIGNUP_CODE).')
    if PRIVATE_MODE and len(d.password)<12:raise HTTPException(422,'La contraseña debe tener al menos 12 caracteres')
    salt,hashed=pbkdf2(d.password)
    with connect() as db:
        try:
            c=db.execute('''INSERT INTO users(username,display_name,salt,passhash,created_at,friend_code)
                    VALUES (?,?,?,?,?,?)''',(d.username.strip().lower(),d.display_name.strip(),salt,hashed,now(),secrets.token_urlsafe(12)))
        except sqlite3.IntegrityError: raise HTTPException(409,'Nombre de usuario no disponible')
        uid=c.lastrowid
        db.execute('INSERT INTO baskets(owner_id,title,kind,created_at,updated_at) VALUES (?,?,?,?,?)',
                   (uid,'Actual','actual',now(),now()))
        token=issue_token(db,uid)
    set_auth_cookie(response,token)
    return {'token':None if PRIVATE_MODE else token,'csrf':csrf_for(token),
            'user':{'id':uid,'display_name':d.display_name.strip(),'username':d.username.strip().lower()}}

@app.post('/api/auth/login')
def login(d:Login,response:Response,req:Request):
    addr=req.client.host if req.client else 'unknown'
    login_limit(addr,d.username,False)
    with connect() as db:
        row=one(db,'SELECT * FROM users WHERE username=?',(d.username.strip().lower(),))
        if not row:
            login_limit(addr,d.username,True)
            raise HTTPException(401,'Credenciales incorrectas')
        _,hashed=pbkdf2(d.password,row['salt'])
        if not hmac.compare_digest(hashed,row['passhash']):
            login_limit(addr,d.username,True)
            raise HTTPException(401,'Credenciales incorrectas')
        login_limit(addr,d.username,False)
        token=issue_token(db,row['id'])
    set_auth_cookie(response,token)
    return {'token':None if PRIVATE_MODE else token,'csrf':csrf_for(token),
            'user':{'id':row['id'],'display_name':row['display_name'],'username':row['username']}}

@app.get('/api/auth/session')
def browser_session(req:Request,c:HTTPAuthorizationCredentials|None=Depends(bearer),user=Depends(auth)):
    token=session_token(req,c)
    return {'user':user,'csrf':csrf_for(token)}

@app.post('/api/auth/logout')
def logout(req:Request,response:Response,c:HTTPAuthorizationCredentials|None=Depends(bearer),user=Depends(auth)):
    token=session_token(req,c)
    with connect() as db:db.execute('DELETE FROM sessions WHERE token_digest=?',(token_hash(token),))
    response.delete_cookie(COOKIE_NAME,path='/')
    return {'ok':True}

class ChangePassword(BaseModel):
    current_password:str
    new_password:str=Field(min_length=12,max_length=128)

@app.post('/api/auth/change-password')
def change_password(d:ChangePassword,req:Request,response:Response,
                    c:HTTPAuthorizationCredentials|None=Depends(bearer),user=Depends(auth)):
    with connect() as db:
        row=one(db,'SELECT salt,passhash FROM users WHERE id=?',(user['id'],))
        _,old_hash=pbkdf2(d.current_password,row['salt'])
        if not hmac.compare_digest(old_hash,row['passhash']):raise HTTPException(403,'Contraseña actual incorrecta')
        salt,digest=pbkdf2(d.new_password)
        db.execute('UPDATE users SET salt=?,passhash=? WHERE id=?',(salt,digest,user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        token=issue_token(db,user['id'])
    set_auth_cookie(response,token)
    return {'csrf':csrf_for(token),'ok':True,'message':'Contraseña cambiada; otras sesiones cerradas'}

@app.get('/api/me')
def me(user=Depends(auth)):return user

def bootstrap_data(db,uid):
    baskets=many(db,'''SELECT b.*,CASE WHEN b.owner_id=? THEN 'owner' ELSE m.role END AS my_role,
          (SELECT COUNT(*) FROM basket_items i WHERE i.basket_id=b.id)+(SELECT COUNT(*) FROM basket_free_items fi WHERE fi.basket_id=b.id) item_count,
          u.display_name owner_name
          FROM baskets b JOIN users u ON u.id=b.owner_id
          LEFT JOIN basket_members m ON m.basket_id=b.id AND m.user_id=?
          WHERE b.owner_id=? OR m.user_id=? ORDER BY CASE WHEN b.kind='actual' AND b.owner_id=? THEN 0 ELSE 1 END,b.updated_at DESC''',
          (uid,uid,uid,uid,uid))
    pantry=many(db,'''SELECT pa.*,p.name product_name FROM pantry pa LEFT JOIN products p ON p.id=pa.product_id
       WHERE pa.user_id=? ORDER BY pa.state!='active',pa.expires_on IS NULL,pa.expires_on,pa.id DESC''',(uid,))
    friend_rows=many(db,'''SELECT u.id,u.display_name,u.username FROM friendships f JOIN users u
       ON u.id=CASE WHEN f.u_low=? THEN f.u_high ELSE f.u_low END
       WHERE f.u_low=? OR f.u_high=? ORDER BY u.display_name''',(uid,uid,uid))
    reports=many(db,'''SELECT r.*,u.display_name reporter_name,s.name store_name,p.name product_name,
       (SELECT COUNT(*) FROM live_confirmations c WHERE c.report_id=r.id) confirmations,
       (SELECT COUNT(*) FROM live_flags f WHERE f.report_id=r.id) flags,
       EXISTS(SELECT 1 FROM live_confirmations c WHERE c.report_id=r.id AND c.user_id=?) AS i_confirmed
       FROM live_reports r JOIN users u ON u.id=r.reporter_id JOIN stores s ON s.id=r.store_id
       JOIN products p ON p.id=r.product_id
       WHERE r.expires_at>? AND r.status='open'
       ORDER BY r.created_at DESC LIMIT 100''',(uid,now()))
    price_rows=many(db,'''SELECT x.*,p.name product_name,s.name store_name,u.display_name reporter_name
       FROM price_observations x JOIN products p ON p.id=x.product_id
       JOIN stores s ON s.id=x.store_id JOIN users u ON u.id=x.user_id
       ORDER BY x.observed_at DESC LIMIT 150''')
    reviews=many(db,'''SELECT r.*,u.display_name reviewer_name,p.name product_name
       FROM reviews r JOIN users u ON u.id=r.user_id JOIN products p ON p.id=r.product_id
       ORDER BY r.updated_at DESC LIMIT 80''')
    net=many(db,'''SELECT ps.place_id,ps.store_id,s.name store_name FROM place_stores ps
            JOIN places p ON p.id=ps.place_id AND p.user_id=? JOIN stores s ON s.id=ps.store_id''',(uid,))
    return {
      'me':one(db,'SELECT id,username,display_name,friend_code FROM users WHERE id=?',(uid,)),
      'baskets':baskets,'basket_preferences':many(db,'''SELECT bsp.basket_id,bsp.store_id,s.name store_name,s.chain
              FROM basket_store_preferences bsp JOIN stores s ON s.id=bsp.store_id
              JOIN baskets b ON b.id=bsp.basket_id LEFT JOIN basket_members m ON m.basket_id=b.id AND m.user_id=?
              WHERE b.owner_id=? OR m.user_id=?''',(uid,uid,uid)),'pantry':pantry,'friends':friend_rows,'reports':reports,'prices':price_rows,
      'reviews':reviews,'network':net,'places':many(db,'SELECT * FROM places WHERE user_id=? ORDER BY id DESC',(uid,)),
      'products':many(db,'''SELECT p.*,b.name brand_name,g.name group_name,b.evidence_url brand_evidence
          FROM products p LEFT JOIN brands b ON b.id=p.brand_id LEFT JOIN groups g ON g.id=b.group_id ORDER BY p.id'''),
      'brands':many(db,'''SELECT b.*,g.name group_name,g.evidence_url group_source FROM brands b JOIN groups g ON g.id=b.group_id'''),
      'stores':many(db,'SELECT * FROM stores ORDER BY chain,name LIMIT 3000'),
      'drafts':many(db,'SELECT id,mode,window_start,window_mins,notice_hours,recipient_alias,status,created_at FROM order_drafts WHERE user_id=? ORDER BY id DESC',(uid,)),
      'watches':many(db,'''SELECT w.*,p.name product_name,s.name store_name
           FROM price_watches w JOIN products p ON p.id=w.product_id LEFT JOIN stores s ON s.id=w.store_id
           WHERE w.user_id=? ORDER BY w.id DESC''',(uid,)),
      'watch_alerts':watch_alerts(db,uid),
      'family_tasks':family_tasks_for(db,uid),
      'trusted_help_requests':help_requests_for(db,uid),
      'shopping_runs':many(db,'''SELECT * FROM shopping_runs WHERE user_id=? ORDER BY recorded_at DESC LIMIT 40''',(uid,)),
      'recent_movements':many(db,'''SELECT m.*,pa.unit,p.name product_name,pa.custom_name
             FROM pantry_movements m JOIN pantry pa ON pa.id=m.pantry_id
             LEFT JOIN products p ON p.id=pa.product_id WHERE m.user_id=? ORDER BY m.id DESC LIMIT 30''',(uid,)),
      'shopper':one(db,'SELECT * FROM shopper_profiles WHERE user_id=?',(uid,)) or {'status':'not_applied'},
      'demo_mode':not PRIVATE_MODE and os.getenv('SHOPPER_DEMO','0')=='1',
      'disclaimer':'Datos colaborativos sin verificar; ninguna reserva, compra o empleo es real.'}

@app.get('/api/bootstrap')
def bootstrap(user=Depends(auth)):
    with connect() as db:return bootstrap_data(db,user['id'])

# ------- Baskets, actual basket, invitations, friends -------
class NewBasket(BaseModel):
    title:str=Field(min_length=1,max_length=90)
    kind:str='ocasional'
    notes:str=Field(default='',max_length=700)
    event_on:date|None=None
    budget_cents:int|None=Field(default=None,ge=0,le=5_000_000)
    place_id:int|None=None
    cover_emoji:str=Field(default='🧺',min_length=1,max_length=8)
    accent:str='sage'
    topics:list[str]=Field(default_factory=list,max_length=6)
    preferred_store_ids:list[int]=Field(default_factory=list,max_length=25)

KINDS={'actual','semanal','mensual','evento','ocasional'}
ACCENTS={'sage','peach','lavender','ocean','lemon','rose'}
TOPICS={'frescos','despensa','limpieza','mascotas','bebidas','celebracion','salud','otros'}


def validate_basket_options(db,owner_id:int,kind:str,place_id:int|None,event_on:date|None,
                            accent:str,topics:list[str],store_ids:list[int]):
    if kind not in KINDS:raise HTTPException(400,'Tipo de cesta no válido')
    if kind!='evento' and event_on is not None:
        raise HTTPException(400,'La fecha de evento solo está disponible para cestas de tipo Evento')
    if accent not in ACCENTS:raise HTTPException(400,'Color de portada no permitido')
    if len(topics)!=len(set(topics)) or not set(topics).issubset(TOPICS):
        raise HTTPException(400,'Temas duplicados o desconocidos')
    if len(store_ids)!=len(set(store_ids)) or any(type(i) is not int or i<1 for i in store_ids):
        raise HTTPException(400,'Tiendas duplicadas o incorrectas')
    if place_id is not None:own_place(db,place_id,owner_id)
    if store_ids and place_id is None:
        raise HTTPException(400,'Primero elige un lugar y configura su red de tiendas')
    if store_ids:
        q=','.join('?' for _ in store_ids)
        found=db.execute(f'SELECT COUNT(*) FROM place_stores WHERE place_id=? AND store_id IN ({q})',
                         (place_id,*store_ids)).fetchone()[0]
        if found!=len(store_ids):raise HTTPException(400,'Solo puedes elegir tiendas de la red del lugar seleccionado')

@app.post('/api/baskets')
def create_basket(d:NewBasket,user=Depends(auth)):
    if d.kind=='actual':raise HTTPException(400,'La cesta Actual ya existe')
    with connect() as db:
        validate_basket_options(db,user['id'],d.kind,d.place_id,d.event_on,d.accent,d.topics,d.preferred_store_ids)
        c=db.execute('''INSERT INTO baskets(owner_id,title,kind,place_id,event_on,budget_cents,notes,created_at,updated_at,cover_emoji,accent,topics_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',(user['id'],d.title.strip(),d.kind,d.place_id,d.event_on.isoformat() if d.event_on else None,d.budget_cents,d.notes.strip(),now(),now(),d.cover_emoji,d.accent,json.dumps(d.topics,ensure_ascii=False)))
        if d.preferred_store_ids:
            db.executemany('INSERT INTO basket_store_preferences(basket_id,store_id) VALUES (?,?)',
                           [(c.lastrowid,i) for i in d.preferred_store_ids])
        return {'id':c.lastrowid}

class EditBasket(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=90)
    kind:str|None=None
    place_id:int|None=None
    event_on:date|None=None
    notes:str|None=Field(default=None,max_length=700)
    budget_cents:int|None=Field(default=None,ge=0,le=5_000_000)
    cover_emoji:str|None=Field(default=None,min_length=1,max_length=8)
    accent:str|None=None
    topics:list[str]|None=Field(default=None,max_length=6)
    preferred_store_ids:list[int]|None=Field(default=None,max_length=25)

@app.patch('/api/baskets/{bid}')
def edit_basket(bid:int,d:EditBasket,user=Depends(auth)):
    data=d.model_dump(exclude_unset=True)
    if not data:return {'ok':True}
    with connect() as db:
        b=basket_access(db,bid,user['id'],owner=True)
        kind=data.get('kind',b['kind'])
        if b['kind']=='actual' and kind!='actual':raise HTTPException(409,'La cesta Actual debe mantenerse')
        if b['kind']!='actual' and kind=='actual':raise HTTPException(409,'Ya tienes cesta Actual')
        place=data.get('place_id',b['place_id'])
        event=data.get('event_on',date.fromisoformat(b['event_on']) if b['event_on'] else None)
        if kind!='evento' and 'event_on' not in data:event=None
        topics=data.get('topics',json.loads(b['topics_json']))
        if topics is None:topics=[]
        selected=data.get('preferred_store_ids')
        if selected is None:
            selected=[r['store_id'] for r in many(db,'SELECT store_id FROM basket_store_preferences WHERE basket_id=?',(bid,))]
            if place!=b['place_id']:
                selected=[]  # changing the place invalidates its previous store preferences
        validate_basket_options(db,b['owner_id'],kind,place,event,data.get('accent',b['accent']),topics,selected)
        fields={k:v for k,v in data.items() if k not in ('topics','preferred_store_ids')}
        if kind!='evento':fields['event_on']=None
        if 'topics' in data:fields['topics_json']=json.dumps(topics,ensure_ascii=False)
        fields['updated_at']=now()
        fields={k:v.isoformat() if isinstance(v,date) else v for k,v in fields.items()}
        db.execute('UPDATE baskets SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',tuple(fields.values())+(bid,))
        if 'preferred_store_ids' in data or place!=b['place_id']:
            db.execute('DELETE FROM basket_store_preferences WHERE basket_id=?',(bid,))
            if selected:
                db.executemany('INSERT INTO basket_store_preferences(basket_id,store_id) VALUES (?,?)',[(bid,i) for i in selected])
        return {'ok':True}

@app.get('/api/baskets/{bid}')
def get_basket(bid:int,user=Depends(auth)):
    with connect() as db:
        b=basket_access(db,bid,user['id'])
        items=many(db,'''SELECT i.product_id,i.quantity,i.checked,i.checked_by,i.checked_at,p.name,p.category,p.gtin,p.format_text
            FROM basket_items i JOIN products p ON p.id=i.product_id WHERE i.basket_id=? ORDER BY p.name''',(bid,))
        for i in items:i['item_kind']='catalog'
        free=many(db,'''SELECT id free_id,NULL product_id,quantity,title name,'Anotación manual' category,NULL gtin,'' format_text,
                      checked,checked_by,checked_at FROM basket_free_items WHERE basket_id=? ORDER BY id''',(bid,))
        for i in free:i['item_kind']='free'
        items+=free
        members=many(db,'''SELECT u.id,u.display_name,m.role FROM basket_members m JOIN users u ON u.id=m.user_id
             WHERE m.basket_id=? ORDER BY u.display_name''',(bid,))
        return {'basket':b,'items':items,'members':members,'checked_count':sum(bool(i['checked']) for i in items),'preferred_store_ids':[r['store_id'] for r in many(db,'SELECT store_id FROM basket_store_preferences WHERE basket_id=?',(bid,))],'topics':json.loads(b['topics_json']),'my_role':'owner' if b['owner_id']==user['id'] else one(db,'SELECT role FROM basket_members WHERE basket_id=? AND user_id=?',(bid,user['id']))['role']}

class Quantity(BaseModel):
    quantity:float=Field(ge=0,le=1000)

@app.put('/api/baskets/{bid}/items/{pid}')
def put_item(bid:int,pid:int,d:Quantity,user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'],write=True);existing(db,'products',pid)
        if d.quantity==0:db.execute('DELETE FROM basket_items WHERE basket_id=? AND product_id=?',(bid,pid))
        else:db.execute('''INSERT INTO basket_items(basket_id,product_id,quantity) VALUES (?,?,?)
                 ON CONFLICT(basket_id,product_id) DO UPDATE SET quantity=excluded.quantity''',(bid,pid,d.quantity))
        db.execute('UPDATE baskets SET updated_at=? WHERE id=?',(now(),bid))
        return {'ok':True}

@app.post('/api/baskets/{bid}/duplicate')
def duplicate_basket(bid:int,user=Depends(auth)):
    with connect() as db:
        b=basket_access(db,bid,user['id'])
        c=db.execute('''INSERT INTO baskets(owner_id,title,kind,place_id,event_on,budget_cents,notes,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?)''',(user['id'],b['title']+' · copia','ocasional',
                 b['place_id'] if b['owner_id']==user['id'] else None,None,b['budget_cents'],b['notes'],now(),now()))
        if b['owner_id']==user['id']:
            db.execute('INSERT INTO basket_store_preferences(basket_id,store_id) SELECT ?,store_id FROM basket_store_preferences WHERE basket_id=?',(c.lastrowid,bid))
        db.execute('INSERT INTO basket_items(basket_id,product_id,quantity,checked) SELECT ?,product_id,quantity,0 FROM basket_items WHERE basket_id=?',(c.lastrowid,bid))
        db.execute('INSERT INTO basket_free_items(basket_id,title,quantity,created_at) SELECT ?,title,quantity,? FROM basket_free_items WHERE basket_id=?',(c.lastrowid,now(),bid))
        return {'id':c.lastrowid}

@app.delete('/api/baskets/{bid}')
def delete_basket(bid:int,user=Depends(auth)):
    with connect() as db:
        b=basket_access(db,bid,user['id'],owner=True)
        if b['kind']=='actual':raise HTTPException(409,'No puedes eliminar tu cesta Actual')
        # Order drafts are immutable history. If drafts exist, keep a basket instead of deleting it.
        if one(db,'SELECT id FROM order_drafts WHERE basket_id=?',(bid,)):
            raise HTTPException(409,'Esta cesta tiene borradores de pedido; duplica para continuar sin borrarlos')
        db.execute('DELETE FROM invite_codes WHERE kind=? AND resource_id=?',('basket',bid))
        db.execute('DELETE FROM baskets WHERE id=?',(bid,))
        return {'ok':True}

class InviteRequest(BaseModel):
    role:str='editor'

def make_invite(db,kind,resource_id,uid,role=None):
    code=secrets.token_urlsafe(18)
    exp=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(timespec='seconds')
    db.execute('INSERT INTO invite_codes(code_digest,kind,resource_id,created_by,role,expires_at) VALUES (?,?,?,?,?,?)',
          (token_hash(code),kind,resource_id,uid,role,exp))
    return {'code':code,'expires_at':exp,'one_time':True}

@app.post('/api/baskets/{bid}/invite')
def basket_invite(bid:int,d:InviteRequest,user=Depends(auth)):
    if d.role not in ('editor','reader'):raise HTTPException(400,'Permiso no admitido')
    with connect() as db:
        basket_access(db,bid,user['id'],owner=True)
        return make_invite(db,'basket',bid,user['id'],d.role)

@app.post('/api/friends/invite')
def friend_invite(user=Depends(auth)):
    with connect() as db:return make_invite(db,'friend',user['id'],user['id'])

class ClaimCode(BaseModel):
    code:str=Field(min_length=15,max_length=120)

@app.post('/api/invitations/redeem')
def redeem_invite(d:ClaimCode,user=Depends(auth)):
    with connect() as db:
        invite=one(db,'SELECT * FROM invite_codes WHERE code_digest=?',(token_hash(d.code.strip()),))
        if not invite or invite['claimed_by'] or invite['expires_at']<=now():raise HTTPException(404,'Invitación inválida, usada o caducada')
        if invite['created_by']==user['id']:raise HTTPException(400,'No puedes aceptar tu propia invitación')
        if invite['kind']=='basket':
            b=existing(db,'baskets',invite['resource_id'])
            db.execute('''INSERT INTO basket_members(basket_id,user_id,role,created_at) VALUES (?,?,?,?)
                  ON CONFLICT(basket_id,user_id) DO UPDATE SET role=excluded.role''',
                  (b['id'],user['id'],invite['role'],now()))
            outcome='Cesta compartida con tu perfil'
        elif invite['kind']=='friend':
            low,high=sorted([invite['created_by'],user['id']])
            db.execute('INSERT OR IGNORE INTO friendships(u_low,u_high,created_at) VALUES (?,?,?)',(low,high,now()))
            outcome='Amistad aceptada por ambos mediante el código'
        else:raise HTTPException(400,'Invitación desconocida')
        # Atomic single-use: SQLite serialises writes and the UPDATE only succeeds if unclaimed.
        cur=db.execute('UPDATE invite_codes SET claimed_by=?,claimed_at=? WHERE code_digest=? AND claimed_by IS NULL',
                       (user['id'],now(),invite['code_digest']))
        if cur.rowcount!=1:raise HTTPException(409,'La invitación ya se ha utilizado')
        return {'ok':True,'message':outcome}

# ------- places, stores and network -------
class Place(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    address:str|None=Field(default=None,max_length=220)
    lat:float|None=Field(default=None,ge=-90,le=90)
    lon:float|None=Field(default=None,ge=-180,le=180)

@app.post('/api/places')
def add_place(d:Place,user=Depends(auth)):
    if (d.lat is None) != (d.lon is None):raise HTTPException(400,'Latitud y longitud deben indicarse juntas')
    with connect() as db:
        c=db.execute('INSERT INTO places(user_id,name,address,lat,lon,created_at) VALUES (?,?,?,?,?,?)',
                     (user['id'],d.name.strip(),d.address.strip() if d.address else None,d.lat,d.lon,now()))
        return {'id':c.lastrowid,'note':'Ubicación guardada de forma privada en esta alfa local'}

class Store(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    chain:str=Field(min_length=2,max_length=80)
    address:str=Field(min_length=6,max_length=230)
    municipality:str=Field(default='',max_length=80)
    lat:float|None=Field(default=None,ge=-90,le=90)
    lon:float|None=Field(default=None,ge=-180,le=180)

@app.post('/api/stores')
def add_store(d:Store,user=Depends(auth)):
    if (d.lat is None) != (d.lon is None):raise HTTPException(400,'Coordenadas incompletas')
    with connect() as db:
        existing_store=one(db,'SELECT id FROM stores WHERE lower(name)=lower(?) AND lower(address)=lower(?)',(d.name.strip(),d.address.strip()))
        if existing_store:return {'id':existing_store['id'],'duplicate':True}
        c=db.execute('''INSERT INTO stores(name,chain,address,municipality,lat,lon,source_type,added_by)
          VALUES (?,?,?,?,?,?,?,?)''',(d.name.strip(),d.chain.strip(),d.address.strip(),d.municipality.strip(),d.lat,d.lon,'aporte_manual_no_verificado',user['id']))
        return {'id':c.lastrowid,'note':'Aportación sin verificación externa. Sin catálogo oficial ni stock.'}

class StoreLink(BaseModel):
    store_id:int
    save:bool=True

@app.post('/api/places/{place_id}/stores')
def network(place_id:int,d:StoreLink,user=Depends(auth)):
    with connect() as db:
        own_place(db,place_id,user['id']);existing(db,'stores',d.store_id)
        if d.save:db.execute('INSERT OR IGNORE INTO place_stores(place_id,store_id) VALUES (?,?)',(place_id,d.store_id))
        else:db.execute('DELETE FROM place_stores WHERE place_id=? AND store_id=?',(place_id,d.store_id))
        return {'ok':True,'saved':d.save}

# ------- Fast capture, shared shopping progress, invitation lifecycle -------
class FreeItem(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    quantity:float=Field(default=1,gt=0,le=1000)

@app.post('/api/baskets/{bid}/free-items')
def quick_add_item(bid:int,d:FreeItem,user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'],write=True)
        c=db.execute('INSERT INTO basket_free_items(basket_id,title,quantity,created_at) VALUES (?,?,?,?)',
          (bid,d.title.strip(),d.quantity,now()))
        db.execute('UPDATE baskets SET updated_at=? WHERE id=?',(now(),bid))
        return {'id':c.lastrowid,'note':'Anotación de cesta, no referencia de catálogo. No se publicará en Foodpedia.'}

class FreePatch(BaseModel):
    quantity:float|None=Field(default=None,ge=0,le=1000)
    checked:bool|None=None

@app.patch('/api/baskets/{bid}/free-items/{fid}')
def free_item_patch(bid:int,fid:int,d:FreePatch,user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'],write=True)
        item=one(db,'SELECT * FROM basket_free_items WHERE id=? AND basket_id=?',(fid,bid))
        if not item:raise HTTPException(404,'Anotación no encontrada')
        if d.quantity is not None:
            if d.quantity==0:db.execute('DELETE FROM basket_free_items WHERE id=?',(fid,))
            else:db.execute('UPDATE basket_free_items SET quantity=? WHERE id=?',(d.quantity,fid))
        if d.checked is not None and d.quantity!=0:
            db.execute('UPDATE basket_free_items SET checked=?,checked_by=?,checked_at=? WHERE id=?',
                       (int(d.checked),user['id'] if d.checked else None,now() if d.checked else None,fid))
        db.execute('UPDATE baskets SET updated_at=? WHERE id=?',(now(),bid))
        return {'ok':True}

class ItemCheck(BaseModel):
    checked:bool

@app.patch('/api/baskets/{bid}/items/{pid}/check')
def checked_catalog_item(bid:int,pid:int,d:ItemCheck,user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'],write=True)
        r=one(db,'SELECT product_id FROM basket_items WHERE basket_id=? AND product_id=?',(bid,pid))
        if not r:raise HTTPException(404,'Producto no incluido en la cesta')
        db.execute('UPDATE basket_items SET checked=?,checked_by=?,checked_at=? WHERE basket_id=? AND product_id=?',
              (int(d.checked),user['id'] if d.checked else None,now() if d.checked else None,bid,pid))
        db.execute('UPDATE baskets SET updated_at=? WHERE id=?',(now(),bid))
        return {'ok':True}

@app.post('/api/baskets/{bid}/reset-checks')
def reset_basket_checks(bid:int,user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'],write=True)
        db.execute('UPDATE basket_items SET checked=0,checked_by=NULL,checked_at=NULL WHERE basket_id=?',(bid,))
        db.execute('UPDATE basket_free_items SET checked=0,checked_by=NULL,checked_at=NULL WHERE basket_id=?',(bid,))
        db.execute('UPDATE baskets SET updated_at=? WHERE id=?',(now(),bid))
        return {'ok':True}

@app.delete('/api/baskets/{bid}/members/{member}')
def remove_basket_member(bid:int,member:int,user=Depends(auth)):
    with connect() as db:
        b=basket_access(db,bid,user['id'])
        if user['id']!=member and b['owner_id']!=user['id']:
            raise HTTPException(403,'Solo puedes abandonar una cesta o retirar a miembros si eres propietario')
        if member==b['owner_id']:raise HTTPException(409,'El propietario no puede abandonar su cesta')
        if not one(db,'SELECT 1 found FROM basket_members WHERE basket_id=? AND user_id=?',(bid,member)):
            raise HTTPException(404,'Persona no pertenece a la cesta')
        db.execute('DELETE FROM basket_members WHERE basket_id=? AND user_id=?',(bid,member))
        return {'ok':True}

@app.delete('/api/friends/{other_id}')
def remove_friend(other_id:int,user=Depends(auth)):
    if other_id==user['id']:raise HTTPException(400,'No eres tu propio amigo')
    low,high=sorted([other_id,user['id']])
    with connect() as db:
        db.execute('DELETE FROM friendships WHERE u_low=? AND u_high=?',(low,high))
    return {'ok':True,'note':'Las cestas compartidas se administran separadamente'}

# ------- product graph, barcode -------
def gtin_valid(code):
    if not re.fullmatch(r'(?:\d{8}|\d{12}|\d{13}|\d{14})',code):return False
    digits=list(map(int,code))
    check=(10-sum(n*(3 if i%2==0 else 1) for i,n in enumerate(reversed(digits[:-1])))%10)%10
    return check==digits[-1]

class Product(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    category:str=Field(min_length=2,max_length=70)
    gtin:str|None=None
    format_text:str=Field(default='',max_length=35)
    ingredients:str|None=Field(default=None,max_length=1200)
    allergens:str|None=Field(default=None,max_length=450)
    origin_note:str|None=Field(default=None,max_length=300)

@app.post('/api/products')
def add_product(d:Product,user=Depends(auth)):
    if d.gtin and not gtin_valid(d.gtin):raise HTTPException(400,'Código EAN/GTIN inválido')
    with connect() as db:
        if d.gtin:
            dup=one(db,'SELECT id FROM products WHERE gtin=?',(d.gtin,))
            if dup:return {'id':dup['id'],'duplicate':True}
        c=db.execute('''INSERT INTO products(name,gtin,category,format_text,ingredients,allergens,origin_note,source_status,added_by,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)''',
           (d.name.strip(),d.gtin,d.category.strip(),d.format_text.strip(),d.ingredients,d.allergens,d.origin_note,'Aporte manual NO verificado',user['id'],now()))
        return {'id':c.lastrowid,'note':'No se infiere presencia, stock, nutrición ni origen de un código'}

@app.get('/api/barcodes/{code}')
def barcode(code:str,user=Depends(auth)):
    if not gtin_valid(code):raise HTTPException(400,'Código de barras inválido')
    with connect() as db:product=one(db,'SELECT * FROM products WHERE gtin=?',(code,))
    return {'found':bool(product),'product':product,'external_lookup':False,
            'note':'Consulta local. Open Food Facts no está conectado en esta versión; no confirma stock ni precio.'}

# User-triggered lookup only; no crawling, inventory or automatic data import.
# OFF requires a identifying user agent, e.g. SHOPPER/8.0 (contact@example.org).
_OFF_CALLS=deque()
_OFF_LOCK=Lock()

@app.get('/api/barcodes/{code}/external')
def off_lookup(code:str,user=Depends(auth)):
    if not gtin_valid(code):raise HTTPException(400,'Código de barras inválido')
    user_agent=os.getenv('SHOPPER_OFF_USER_AGENT','').strip()
    if not re.fullmatch(r'.{2,90}/[0-9.]+ \([^\s()@]+@[^\s()@]+\)',user_agent):
        raise HTTPException(503,'Para consultar Open Food Facts, configura SHOPPER_OFF_USER_AGENT con una dirección de contacto válida; mira el README')
    with _OFF_LOCK:
        t=time.monotonic()
        while _OFF_CALLS and _OFF_CALLS[0]<t-60:_OFF_CALLS.popleft()
        if len(_OFF_CALLS)>=8:raise HTTPException(429,'Límite de consultas externas del piloto: máximo 8 por minuto')
        _OFF_CALLS.append(t)
    url=f'https://world.openfoodfacts.org/api/v3.6/product/{code}.json'
    request=urllib.request.Request(url,headers={'User-Agent':user_agent,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=6) as response:
            data=json.loads(response.read(1_000_000).decode('utf-8'))
    except (urllib.error.URLError,TimeoutError,ValueError,UnicodeError,OverflowError) as exc:
        raise HTTPException(502,'Open Food Facts no ha respondido correctamente; inténtalo más tarde') from exc
    product=data.get('product') if isinstance(data,dict) else None
    if not isinstance(product,dict) or not product:
        return {'found':False,'source':'Open Food Facts','url':f'https://world.openfoodfacts.org/product/{code}',
                'note':'Sin ficha disponible, no implica inexistencia comercial'}
    return {'found':True,'source':'Open Food Facts','url':f'https://world.openfoodfacts.org/product/{code}',
          'name':str(product.get('product_name_es') or product.get('product_name') or '')[:160],
          'brands':str(product.get('brands') or '')[:120],
          'quantity':str(product.get('quantity') or '')[:80],
          'ingredients':str(product.get('ingredients_text_es') or product.get('ingredients_text') or '')[:750],
          'allergens':str(product.get('allergens') or '')[:200],
          'nutriscore_grade':str(product.get('nutriscore_grade') or '')[:2],
          'note':'Información de una base colaborativa externa: comprueba siempre la etiqueta. No acredita venta, stock ni precio. No se ha importado al catálogo de SHOPPER.'}

class Review(BaseModel):
    product_id:int
    quality:int=Field(ge=1,le=5)
    value:int=Field(ge=1,le=5)
    comment:str=Field(min_length=3,max_length=600)

@app.post('/api/reviews')
def add_review(d:Review,user=Depends(auth)):
    with connect() as db:
        existing(db,'products',d.product_id)
        db.execute('''INSERT INTO reviews(user_id,product_id,quality,value,comment,updated_at) VALUES(?,?,?,?,?,?)
         ON CONFLICT(user_id,product_id) DO UPDATE SET quality=excluded.quality,value=excluded.value,
           comment=excluded.comment,updated_at=excluded.updated_at''',
           (user['id'],d.product_id,d.quality,d.value,d.comment.strip(),now()))
        return {'ok':True,'note':'Opinión subjetiva; no es evaluación nutricional ni garantía de calidad'}

# ------- pantry -------
class Pantry(BaseModel):
    product_id:int|None=None
    custom_name:str|None=Field(default=None,max_length=100)
    quantity:float=Field(gt=0,le=10000)
    unit:str='ud'
    expires_on:date|None=None
    estimated_value_cents:int|None=Field(default=None,ge=0,le=1000000)

@app.post('/api/pantry')
def pantry_add(d:Pantry,user=Depends(auth)):
    if d.unit not in ('ud','g','kg','ml','l'):raise HTTPException(400,'Unidad incorrecta')
    if d.product_id is None and not (d.custom_name or '').strip():raise HTTPException(400,'Selecciona producto o indica un nombre')
    with connect() as db:
        if d.product_id:existing(db,'products',d.product_id)
        c=db.execute('''INSERT INTO pantry(user_id,product_id,custom_name,quantity,unit,expires_on,estimated_value_cents,created_at)
              VALUES(?,?,?,?,?,?,?,?)''',
               (user['id'],d.product_id,(d.custom_name or '').strip() or None,d.quantity,d.unit,
                d.expires_on.isoformat() if d.expires_on else None,d.estimated_value_cents,now()))
        return {'id':c.lastrowid}

class PantryStatus(BaseModel):
    state:str

@app.patch('/api/pantry/{pid}')
def pantry_close(pid:int,d:PantryStatus,user=Depends(auth)):
    if d.state not in ('used','discarded'):raise HTTPException(400,'Estado no válido')
    with connect() as db:
        row=one(db,'SELECT * FROM pantry WHERE id=? AND user_id=?',(pid,user['id']))
        if not row:raise HTTPException(404,'No existe este artículo de tu despensa')
        if row['state']!='active':raise HTTPException(409,'Este artículo ya está cerrado')
        db.execute('UPDATE pantry SET state=?,closed_at=? WHERE id=?',(d.state,now(),pid))
        db.execute('INSERT INTO pantry_movements(pantry_id,user_id,quantity,kind,created_at) VALUES(?,?,?,?,?)',
                   (pid,user['id'],row['quantity'],d.state,now()))
        return {'ok':True,'methodology':'Registro declarado, no demuestra kg o € evitados causalmente'}

# ------- prices and optimizer -------
class Price(BaseModel):
    product_id:int
    store_id:int
    amount_cents:int=Field(ge=1,le=1_000_000)
    source_type:str='etiqueta'
    note:str=Field(default='',max_length=200)

@app.post('/api/prices')
def add_price(d:Price,user=Depends(auth)):
    if d.source_type not in ('etiqueta','ticket','anuncio'):raise HTTPException(400,'Tipo de fuente no válido')
    with connect() as db:
        existing(db,'products',d.product_id);existing(db,'stores',d.store_id)
        c=db.execute('''INSERT INTO price_observations(product_id,store_id,user_id,amount_cents,source_type,note,observed_at)
              VALUES(?,?,?,?,?,?,?)''',(d.product_id,d.store_id,user['id'],d.amount_cents,d.source_type,d.note,now()))
        return {'id':c.lastrowid,'status':'observación_usuario_sin_verificar','note':'No equivale a precio garantizado ni a stock'}

def get_compare(db,bid,uid,days=14,penalty=300):
    basket=basket_access(db,bid,uid)
    items=many(db,'SELECT i.product_id,i.quantity,p.name FROM basket_items i JOIN products p ON p.id=i.product_id WHERE i.basket_id=?',(bid,))
    free=many(db,'SELECT title name FROM basket_free_items WHERE basket_id=?',(bid,))
    selected_stores=many(db,'''SELECT s.* FROM stores s JOIN place_stores ps ON ps.store_id=s.id
        JOIN places pl ON pl.id=ps.place_id WHERE pl.id=? AND pl.user_id=?''',(basket['place_id'],uid)) if basket['place_id'] else []
    if not selected_stores and basket['place_id'] is None:
        selected_stores=many(db,'SELECT * FROM stores ORDER BY id LIMIT 100')
    store_ids=[s['id'] for s in selected_stores]
    if not items and not free:return {'status':'empty','items':[],'by_store':[],'best':None,'unpriced':[],'coverage':0}
    if not store_ids:return {'status':'no_stores','items':items,'by_store':[],'best':None,'unpriced':[i['name'] for i in items]+[i['name'] for i in free],'coverage':0}
    cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat(timespec='seconds')
    rows=many(db,'''SELECT product_id,store_id,amount_cents,source_type,observed_at,id FROM price_observations
             WHERE observed_at>=? ORDER BY observed_at DESC,id DESC''',(cutoff,))
    newest={}
    for r in rows:
        key=(r['product_id'],r['store_id'])
        if key not in newest and r['store_id'] in store_ids:newest[key]=r
    by_store=[]
    for s in selected_stores:
        priced=[];missing=[];total=0
        for i in items:
            r=newest.get((i['product_id'],s['id']))
            if r:
                subtotal=round(i['quantity']*r['amount_cents']);total+=subtotal
                priced.append({'product_id':i['product_id'],'amount_cents':r['amount_cents'],'subtotal_cents':subtotal,'source_type':r['source_type'],'observed_at':r['observed_at']})
            else:missing.append(i['name'])
        by_store.append({'store_id':s['id'],'store_name':s['name'],'covered':len(priced),'missing':missing,
             'total_cents':total if len(priced)==len(items) else None,'partial_total_cents':total,'details':priced})
    # Full basket coverage across 1 or 2 stores; source observations are still unverified.
    candidates=[]
    use_stores=sorted(selected_stores,key=lambda s:sum((i['product_id'],s['id']) in newest for i in items),reverse=True)[:15]
    for n in (1,2):
        for option in itertools.combinations(use_stores,n):
            choices=[];raw_total=0
            for i in items:
                options=[(newest.get((i['product_id'],s['id'])),s) for s in option]
                available=[(p,s) for p,s in options if p]
                if not available:break
                p,s=min(available,key=lambda x:x[0]['amount_cents'])
                total=round(i['quantity']*p['amount_cents']);raw_total+=total
                choices.append({'product':i['name'],'quantity':i['quantity'],'store_id':s['id'],
                     'store_name':s['name'],'subtotal_cents':total,'amount_cents':p['amount_cents'],
                     'observed_at':p['observed_at'],'source_type':p['source_type']})
            if len(choices)==len(items):
                distinct=len({c['store_id'] for c in choices})
                # Count actual stops, not number of candidate supermarkets.
                score=raw_total+penalty*max(0,distinct-1)
                candidates.append({'stops':distinct,'items_total_cents':raw_total,'extra_stop_assumption_cents':penalty*max(0,distinct-1),
                   'objective_cents':score,'assignment':choices,'store_names':sorted({c['store_name'] for c in choices})})
    best=min(candidates,key=lambda a:(a['objective_cents'],a['stops'])) if candidates and not free else None
    incomplete=[i['name'] for i in items if not any((i['product_id'],sid) in newest for sid in store_ids)]
    complete_ones=[x['total_cents'] for x in by_store if x['total_cents'] is not None]
    baseline=min(complete_ones) if complete_ones else None
    return {'status':'complete' if best else 'insufficient','items':items,'by_store':by_store,'best':best,
        'unpriced':incomplete+[f['name'] for f in free],'coverage':len(items)-len(incomplete),'total_items':len(items)+len(free),
        'single_store_reference_cents':baseline,
        'product_savings_vs_single_cents':baseline-best['items_total_cents'] if (baseline is not None and best) else None,
        'assumption':'Precios aportados por usuarios (últimos '+str(days)+' días); gasto por parada adicional hipotético. No hay datos de stock, tiempo de ruta ni servicio confirmado.'}

@app.get('/api/baskets/{bid}/compare')
def compare(bid:int,days:int=Query(14,ge=1,le=90),extra_stop_cents:int=Query(300,ge=0,le=3000),user=Depends(auth)):
    with connect() as db:return get_compare(db,bid,user['id'],days,extra_stop_cents)

# ------- Waze-like live store reports -------
class Report(BaseModel):
    store_id:int
    product_id:int
    kind:str
    note:str=Field(default='',max_length=280)
    price_cents:int|None=Field(default=None,ge=1,le=1_000_000)

TTL={'agotado':90,'repuesto':120,'descuento':360,'nuevo':720}
@app.post('/api/live')
def live_post(d:Report,user=Depends(auth)):
    if d.kind not in TTL:raise HTTPException(400,'Tipo de aviso desconocido')
    if d.price_cents and d.kind!='descuento':raise HTTPException(400,'Precio solo en avisos de descuento')
    with connect() as db:
        existing(db,'stores',d.store_id);existing(db,'products',d.product_id)
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat(timespec='seconds')
        if one(db,'SELECT id FROM live_reports WHERE reporter_id=? AND store_id=? AND product_id=? AND kind=? AND created_at>?',
               (user['id'],d.store_id,d.product_id,d.kind,cutoff)):
            raise HTTPException(429,'Ya publicaste un aviso similar: prueba más tarde')
        expiry=(datetime.now(timezone.utc)+timedelta(minutes=TTL[d.kind])).isoformat(timespec='seconds')
        c=db.execute('''INSERT INTO live_reports(reporter_id,store_id,product_id,kind,price_cents,note,observed_at,expires_at,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',(user['id'],d.store_id,d.product_id,d.kind,d.price_cents,d.note.strip(),now(),expiry,now()))
        return {'id':c.lastrowid,'status':'no_verificado','expires_at':expiry}

@app.post('/api/live/{rid}/confirm')
def confirm(rid:int,user=Depends(auth)):
    with connect() as db:
        r=existing(db,'live_reports',rid)
        if r['reporter_id']==user['id']:raise HTTPException(400,'No puedes confirmar tu propio aviso')
        if r['status']!='open' or r['expires_at']<=now():raise HTTPException(410,'Aviso cerrado o caducado')
        db.execute('INSERT OR IGNORE INTO live_confirmations(report_id,user_id,created_at) VALUES (?,?,?)',(rid,user['id'],now()))
        return {'ok':True,'note':'Corroboración comunitaria, no stock oficial'}

class Flag(BaseModel):
    reason:str=Field(min_length=3,max_length=160)

@app.post('/api/live/{rid}/flag')
def flag(rid:int,d:Flag,user=Depends(auth)):
    with connect() as db:
        r=existing(db,'live_reports',rid)
        if r['reporter_id']==user['id']:raise HTTPException(400,'No puedes denunciar tu propio aviso')
        db.execute('INSERT OR IGNORE INTO live_flags(report_id,user_id,reason,created_at) VALUES (?,?,?,?)',
                   (rid,user['id'],d.reason,now()))
        if one(db,'SELECT COUNT(*) n FROM live_flags WHERE report_id=?',(rid,))['n']>=3:
            db.execute('UPDATE live_reports SET status=? WHERE id=?',('hidden_pending_review',rid))
        return {'ok':True,'note':'A partir de 3 reportes independientes se oculta hasta revisión'}

# ------- shopper application and order drafts -------
class ShopperPrefs(BaseModel):
    travel_mode:str='walking'
    min_notice_hours:int=Field(default=6,ge=0,le=168)
    min_window_mins:int=60
    max_distance_km:int=Field(default=5,ge=1,le=80)
    availability_note:str=Field(default='',max_length=400)

@app.post('/api/shopper/profile')
def shopper_profile(d:ShopperPrefs,user=Depends(auth)):
    if d.travel_mode not in ('walking','bike','car','transit') or d.min_window_mins not in (15,30,60,120):
        raise HTTPException(400,'Preferencias inválidas')
    with connect() as db:
        current=one(db,'SELECT status FROM shopper_profiles WHERE user_id=?',(user['id'],))
        status=current['status'] if current else 'draft'
        db.execute('''INSERT INTO shopper_profiles(user_id,status,travel_mode,min_notice_hours,min_window_mins,max_distance_km,availability_note,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
            travel_mode=excluded.travel_mode,min_notice_hours=excluded.min_notice_hours,min_window_mins=excluded.min_window_mins,
            max_distance_km=excluded.max_distance_km,availability_note=excluded.availability_note,updated_at=excluded.updated_at''',
            (user['id'],status,d.travel_mode,d.min_notice_hours,d.min_window_mins,d.max_distance_km,d.availability_note,now()))
        return {'status':status,'note':'Configuración de prueba: no concede autorización ni asigna trabajos'}

@app.post('/api/shopper/apply')
def shopper_apply(user=Depends(auth)):
    with connect() as db:
        current=one(db,'SELECT * FROM shopper_profiles WHERE user_id=?',(user['id'],))
        if current and current['status'] not in ('draft','not_applied'):
            raise HTTPException(409,'Ya tienes una solicitud de prueba registrada')
        db.execute('''INSERT INTO shopper_profiles(user_id,status,updated_at) VALUES (?,?,?)
              ON CONFLICT(user_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at''',
              (user['id'],'pending_mock_review',now()))
        return {'status':'pending_mock_review','note':'Solicitud SIMULADA sin alta profesional. Revisión y contratación reales no implementadas.'}

class OrderDraft(BaseModel):
    basket_id:int
    store_id:int|None=None
    place_id:int|None=None
    mode:str
    window_start:str
    window_mins:int
    notice_hours:int=Field(ge=0,le=168)
    recipient_alias:str=Field(default='',max_length=80)

@app.post('/api/order-drafts')
def plan_order(d:OrderDraft,user=Depends(auth)):
    if d.mode not in ('pickup_shopper','delivery_shopper','pickup_store','self_shop'):
        raise HTTPException(400,'Modo inválido')
    if d.window_mins not in (15,30,60,120):raise HTTPException(400,'Ventana de recogida o entrega inválida')
    try:
        local=datetime.fromisoformat(d.window_start)
        if local.tzinfo is None:local=local.replace(tzinfo=ZoneInfo('Europe/Madrid'))
        planned=local.astimezone(timezone.utc)
    except Exception:raise HTTPException(400,'Fecha/hora inválida')
    if planned < datetime.now(timezone.utc)+timedelta(hours=d.notice_hours):
        raise HTTPException(400,'La antelación mínima solicitada no cabe en la fecha elegida')
    with connect() as db:
        b=basket_access(db,d.basket_id,user['id'])
        if d.mode=='pickup_store':
            # Keep disabled even if a store accidentally has prep_integrated=1 in this alpha.
            raise HTTPException(409,'No hay integración autorizada de preparación por supermercado')
        if d.store_id:existing(db,'stores',d.store_id)
        if d.place_id:own_place(db,d.place_id,user['id'])
        if d.mode in ('pickup_shopper','self_shop') and not d.store_id:
            raise HTTPException(400,'Selecciona establecimiento para la recogida o compra propia')
        if d.mode=='delivery_shopper' and not d.place_id:
            raise HTTPException(400,'Selecciona tu lugar guardado para la entrega')
        products=many(db,'''SELECT p.id,p.name,i.quantity FROM basket_items i JOIN products p ON p.id=i.product_id WHERE i.basket_id=?''',(d.basket_id,))
        manual=many(db,'SELECT title name,quantity FROM basket_free_items WHERE basket_id=?',(d.basket_id,))
        if not products and not manual:raise HTTPException(400,'La cesta está vacía')
        snapshot=json.dumps({'basket_title':b['title'],'products':products,'free_text_items':manual,'mode':d.mode},ensure_ascii=False)
        c=db.execute('''INSERT INTO order_drafts(user_id,basket_id,store_id,place_id,mode,window_start,window_mins,notice_hours,
           recipient_alias,shopping_snapshot,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
           (user['id'],d.basket_id,d.store_id,d.place_id,d.mode,local.isoformat(),d.window_mins,d.notice_hours,
            d.recipient_alias.strip(),snapshot,'DRAFT_NOT_SENT',now()))
        return {'id':c.lastrowid,'status':'DRAFT_NOT_SENT','note':'No se ha enviado, cobrado, asignado, preparado ni reservado nada'}

# ------- V8: real user workflows: store shelf, watches, shopping history, pantry movements -------
class Sighting(BaseModel):
    store_id:int
    product_id:int
    kind:str
    note:str=Field(default='',max_length=250)

@app.post('/api/store-sightings')
def store_sighting(d:Sighting,user=Depends(auth)):
    if d.kind not in ('seen','not_found'):raise HTTPException(400,'Tipo de observación inválido')
    with connect() as db:
        existing(db,'stores',d.store_id);existing(db,'products',d.product_id)
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat(timespec='seconds')
        if one(db,'''SELECT id FROM store_sightings WHERE store_id=? AND product_id=? AND user_id=? AND kind=? AND observed_at>?''',
               (d.store_id,d.product_id,user['id'],d.kind,cutoff)):
            raise HTTPException(429,'Ya has registrado esa observación recientemente')
        record=db.execute('INSERT INTO store_sightings(store_id,product_id,user_id,kind,note,observed_at) VALUES(?,?,?,?,?,?)',
                          (d.store_id,d.product_id,user['id'],d.kind,d.note.strip(),now()))
        return {'id':record.lastrowid,'trust':'comunidad_no_verificada','note':'No acredita inventario ni permanencia del producto'}

@app.get('/api/stores/{sid}/shelf')
def shelf(sid:int,user=Depends(auth)):
    with connect() as db:
        store=existing(db,'stores',sid)
        observations=many(db,'''SELECT x.*,p.name product_name,p.gtin,p.format_text,p.category,u.display_name
            FROM store_sightings x JOIN products p ON p.id=x.product_id JOIN users u ON u.id=x.user_id
            WHERE x.store_id=? ORDER BY x.observed_at DESC,x.id DESC''',(sid,))
        recent_prices=many(db,'''SELECT x.product_id,x.amount_cents,x.source_type,x.observed_at,p.name product_name
            FROM price_observations x JOIN products p ON p.id=x.product_id WHERE x.store_id=?
            ORDER BY x.observed_at DESC,x.id DESC''',(sid,))
        cutoff=(datetime.now(timezone.utc)-timedelta(days=14)).isoformat(timespec='seconds')
        rows={}
        for o in observations:
            if o['product_id'] not in rows:
                rows[o['product_id']]={'product_id':o['product_id'],'product_name':o['product_name'],
                  'gtin':o['gtin'],'category':o['category'],'format_text':o['format_text'],
                  'last_seen_kind':o['kind'],'last_seen_at':o['observed_at'],
                  'last_seen_note':o['note'],'price_cents':None,'price_observed_at':None,'price_source':None}
        for pr in recent_prices:
            if pr['observed_at']<cutoff: continue
            if pr['product_id'] not in rows:
                rows[pr['product_id']]={'product_id':pr['product_id'],'product_name':pr['product_name'],
                  'gtin':None,'category':'','format_text':'','last_seen_kind':None,'last_seen_at':None,
                  'last_seen_note':'','price_cents':None,'price_observed_at':None,'price_source':None}
            row=rows[pr['product_id']]
            if row['price_observed_at'] is None:
                row.update(price_cents=pr['amount_cents'],price_observed_at=pr['observed_at'],price_source=pr['source_type'])
        return {'store':{'id':sid,'name':store['name'],'address':store['address']},
                'items':list(rows.values()),'status':'carta_comunitaria_parcial',
                'note':'Solo productos observados por usuarios; no catálogo oficial, disponibilidad ni precio garantizado'}

class Watch(BaseModel):
    product_id:int
    store_id:int|None=None
    threshold_cents:int|None=Field(default=None,ge=1,le=1_000_000)

@app.post('/api/watches')
def watch_add(d:Watch,user=Depends(auth)):
    with connect() as db:
        existing(db,'products',d.product_id)
        if d.store_id is not None:existing(db,'stores',d.store_id)
        price_after=db.execute('SELECT COALESCE(MAX(id),0) FROM price_observations').fetchone()[0]
        report_after=db.execute('SELECT COALESCE(MAX(id),0) FROM live_reports').fetchone()[0]
        old=one(db,'''SELECT id FROM price_watches WHERE user_id=? AND product_id=?
                  AND COALESCE(store_id,0)=COALESCE(?,0)''',(user['id'],d.product_id,d.store_id))
        if old:
            db.execute('UPDATE price_watches SET threshold_cents=?,price_after_id=?,report_after_id=?,created_at=? WHERE id=?',
              (d.threshold_cents,price_after,report_after,now(),old['id']))
            return {'id':old['id'],'updated':True}
        c=db.execute('INSERT INTO price_watches(user_id,product_id,store_id,threshold_cents,created_at,price_after_id,report_after_id) VALUES (?,?,?,?,?,?,?)',
          (user['id'],d.product_id,d.store_id,d.threshold_cents,now(),price_after,report_after))
        return {'id':c.lastrowid,'updated':False,'note':'Solo avisos dentro de SHOPPER; sin notificaciones push'}

@app.delete('/api/watches/{wid}')
def watch_delete(wid:int,user=Depends(auth)):
    with connect() as db:
        c=db.execute('DELETE FROM price_watches WHERE id=? AND user_id=?',(wid,user['id']))
        if not c.rowcount: raise HTTPException(404,'Seguimiento no encontrado')
        return {'ok':True}

def watch_alerts(db,uid):
    watches=many(db,'SELECT * FROM price_watches WHERE user_id=?',(uid,))
    cutoff=(datetime.now(timezone.utc)-timedelta(days=14)).isoformat(timespec='seconds')
    notices=[]
    for w in watches:
        if w['threshold_cents'] is not None:
            prices=many(db,'''SELECT po.id,po.amount_cents,po.store_id,po.observed_at,s.name store_name
                   FROM price_observations po JOIN stores s ON s.id=po.store_id
                   WHERE po.product_id=? AND po.observed_at>=? AND (? IS NULL OR po.store_id=?)
                   ORDER BY po.observed_at DESC,po.id DESC''',(w['product_id'],cutoff,w['store_id'],w['store_id']))
            seen=set()
            for price in prices:
                if price['store_id'] in seen:continue
                seen.add(price['store_id'])
                if price['id']>w['price_after_id'] and price['amount_cents']<=w['threshold_cents']:
                    notices.append({'watch_id':w['id'],'kind':'price','store_name':price['store_name'],
                        'store_id':price['store_id'],'product_id':w['product_id'],
                        'amount_cents':price['amount_cents'],'observed_at':price['observed_at']})
        reports=many(db,'''SELECT r.id,r.kind,r.store_id,r.created_at,s.name store_name
                  FROM live_reports r JOIN stores s ON s.id=r.store_id
                  WHERE r.product_id=? AND r.id>? AND r.expires_at>? AND r.status='open'
                  AND r.kind='repuesto' AND (? IS NULL OR r.store_id=?)
                  ORDER BY r.created_at DESC LIMIT 12''',(w['product_id'],w['report_after_id'],now(),w['store_id'],w['store_id']))
        for r in reports:
            notices.append({'watch_id':w['id'],'kind':'restocked','store_name':r['store_name'],
              'store_id':r['store_id'],'product_id':w['product_id'],'amount_cents':None,'observed_at':r['created_at']})
    return sorted(notices,key=lambda x:x['observed_at'],reverse=True)[:60]

@app.post('/api/baskets/{bid}/copy-to-actual')
def copy_to_actual(bid:int,user=Depends(auth)):
    with connect() as db:
        source=basket_access(db,bid,user['id'])
        target=one(db,"SELECT id FROM baskets WHERE owner_id=? AND kind='actual'",(user['id'],))
        if not target:raise HTTPException(409,'No tienes una cesta Actual')
        if bid==target['id']:raise HTTPException(400,'Ya estás en tu cesta Actual')
        count=0
        for item in many(db,'SELECT product_id,quantity FROM basket_items WHERE basket_id=?',(bid,)):
            db.execute('''INSERT INTO basket_items(basket_id,product_id,quantity)
                VALUES(?,?,?) ON CONFLICT(basket_id,product_id) DO UPDATE SET quantity=basket_items.quantity+excluded.quantity''',
                (target['id'],item['product_id'],item['quantity']))
            count+=1
        for item in many(db,'SELECT title,quantity FROM basket_free_items WHERE basket_id=?',(bid,)):
            db.execute('INSERT INTO basket_free_items(basket_id,title,quantity,created_at) VALUES (?,?,?,?)',
                       (target['id'],item['title'],item['quantity'],now()))
            count+=1
        db.execute('UPDATE baskets SET updated_at=? WHERE id=?',(now(),target['id']))
        return {'ok':True,'target_id':target['id'],'copied_lines':count,
                'note':'Se suman cantidades del catálogo; los artículos de texto se copian como anotaciones'}

class Portion(BaseModel):
    quantity:float=Field(gt=0,le=10000)
    kind:str

@app.post('/api/pantry/{pid}/portion')
def pantry_portion(pid:int,d:Portion,user=Depends(auth)):
    if d.kind not in ('used','discarded'):raise HTTPException(400,'Tipo incorrecto')
    with connect() as db:
        item=one(db,'SELECT * FROM pantry WHERE id=? AND user_id=?',(pid,user['id']))
        if not item:raise HTTPException(404,'Artículo no encontrado')
        if item['state']!='active':raise HTTPException(409,'Artículo ya cerrado')
        if d.quantity>item['quantity']+1e-8:raise HTTPException(400,'No puedes retirar más cantidad de la disponible')
        rest=round(item['quantity']-d.quantity,5)
        db.execute('UPDATE pantry SET quantity=?,state=?,closed_at=? WHERE id=?',
          (rest,d.kind if rest<=1e-8 else 'active',now() if rest<=1e-8 else None,pid))
        db.execute('INSERT INTO pantry_movements(pantry_id,user_id,quantity,kind,created_at) VALUES (?,?,?,?,?)',
          (pid,user['id'],d.quantity,d.kind,now()))
        return {'remaining':rest,'state':d.kind if rest<=1e-8 else 'active',
                'note':'Dato declarado; no estimación causal de desperdicio evitado'}

class ShoppingRun(BaseModel):
    basket_id:int
    store_id:int|None=None
    paid_cents:int=Field(ge=0,le=10_000_000)
    minutes_spent:int|None=Field(default=None,ge=0,le=1440)
    notes:str=Field(default='',max_length=350)

@app.post('/api/shopping-runs')
def shopping_run(d:ShoppingRun,user=Depends(auth)):
    with connect() as db:
        basket=basket_access(db,d.basket_id,user['id'])
        store=existing(db,'stores',d.store_id) if d.store_id is not None else None
        items=many(db,'''SELECT p.name,i.quantity,i.checked FROM basket_items i
              JOIN products p ON p.id=i.product_id WHERE i.basket_id=?''',(d.basket_id,))
        items+=many(db,'SELECT title name,quantity,checked FROM basket_free_items WHERE basket_id=?',(d.basket_id,))
        if not items:raise HTTPException(400,'La cesta está vacía')
        c=db.execute('''INSERT INTO shopping_runs(user_id,basket_id,store_id,basket_name,store_name,paid_cents,minutes_spent,notes,item_snapshot,recorded_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)''',
              (user['id'],d.basket_id,d.store_id,basket['title'],store['name'] if store else None,
               d.paid_cents,d.minutes_spent,d.notes.strip(),json.dumps(items,ensure_ascii=False),now()))
        return {'id':c.lastrowid,'status':'compra_declarada','note':'Importe registrado por el usuario, sin ticket verificado ni ahorro inferido'}

# ------- economic simulator, feedback, own account export -------
class Economics(BaseModel):
    customer_fee_eur:float=Field(ge=0,le=1000)
    worker_eur:float=Field(ge=0,le=1000)
    transport_eur:float=Field(ge=0,le=1000)
    payment_eur:float=Field(ge=0,le=1000)
    support_eur:float=Field(ge=0,le=1000)
    reserve_eur:float=Field(ge=0,le=1000)
    monthly_fixed_eur:float=Field(default=1500,ge=0,le=1e7)

@app.post('/api/economics')
def economics(d:Economics,user=Depends(auth)):
    cost=sum((d.worker_eur,d.transport_eur,d.payment_eur,d.support_eur,d.reserve_eur))
    margin=round(d.customer_fee_eur-cost,2)
    from math import ceil
    return {'contribution_per_order_eur':margin,'variable_costs_eur':round(cost,2),
        'orders_to_cover_fixed':ceil(d.monthly_fixed_eur/margin) if margin>0 else None,
        'note':'Simulación sin IVA, salario del fundador, CAC, impuestos empresariales o efectos logísticos reales.'}

class Feedback(BaseModel):
    area:str=Field(min_length=2,max_length=50)
    note:str=Field(min_length=3,max_length=1000)

@app.post('/api/feedback')
def feedback(d:Feedback,user=Depends(auth)):
    with connect() as db:
        c=db.execute('INSERT INTO feedback(user_id,area,note,created_at) VALUES (?,?,?,?)',(user['id'],d.area,d.note.strip(),now()))
        return {'id':c.lastrowid}

@app.get('/api/account/export')
def export_account(user=Depends(auth)):
    with connect() as db:
        uid=user['id'];data=bootstrap_data(db,uid)
        # Includes only own/authorized baskets and publicly visible community observations; does not export secrets.
        data['basket_details']=[{'id':b['id'],
           'catalog_items':many(db,'SELECT * FROM basket_items WHERE basket_id=?',(b['id'],)),
           'manual_items':many(db,'SELECT * FROM basket_free_items WHERE basket_id=?',(b['id'],))}
           for b in data['baskets']]
        # Public feeds contain other people's contributions. Export only contributions by this user.
        data['my_price_observations']=many(db,'SELECT * FROM price_observations WHERE user_id=?',(uid,))
        data['my_live_reports']=many(db,'SELECT * FROM live_reports WHERE reporter_id=?',(uid,))
        data['my_live_confirmations']=many(db,'SELECT * FROM live_confirmations WHERE user_id=?',(uid,))
        data['my_product_reviews']=many(db,'SELECT * FROM reviews WHERE user_id=?',(uid,))
        data['my_store_sightings']=many(db,'SELECT * FROM store_sightings WHERE user_id=?',(uid,))
        data['my_feedback']=many(db,'SELECT * FROM feedback WHERE user_id=?',(uid,))
        data['my_pantry_movements']=many(db,'SELECT * FROM pantry_movements WHERE user_id=?',(uid,))
        data['my_order_drafts']=many(db,'SELECT * FROM order_drafts WHERE user_id=?',(uid,))
        data['exported_at']=now()
        data.pop('prices',None);data.pop('reports',None);data.pop('reviews',None)
        return JSONResponse(data,headers={'Content-Disposition':'attachment; filename="shopper-mi-cuenta.json"'})


# ------------ Círculo de confianza: recados familiares no comerciales ------------
class FamilyTask(BaseModel):
    basket_id:int
    title:str=Field(min_length=3,max_length=110)
    note:str=Field(default='',max_length=300)
    assigned_to:int|None=None
    due_on:str|None=None
    store_id:int|None=None

def family_tasks_for(db,uid):
    return many(db,"""SELECT t.*,b.title basket_name,u.display_name creator_name,
            a.display_name assignee_name,s.name store_name
          FROM family_tasks t JOIN baskets b ON b.id=t.basket_id
          JOIN users u ON u.id=t.created_by
          LEFT JOIN users a ON a.id=t.assigned_to
          LEFT JOIN stores s ON s.id=t.store_id
          WHERE b.owner_id=? OR EXISTS(SELECT 1 FROM basket_members m
                             WHERE m.basket_id=t.basket_id AND m.user_id=?)
          ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'accepted' THEN 1 ELSE 2 END,
                   t.created_at DESC LIMIT 150""",(uid,uid))

@app.get('/api/family/tasks')
def family_tasks(user=Depends(auth)):
    with connect() as db:return family_tasks_for(db,user['id'])

@app.post('/api/family/tasks')
def family_task_add(d:FamilyTask,user=Depends(auth)):
    with connect() as db:
        basket_access(db,d.basket_id,user['id'],write=True)
        if d.assigned_to is not None:
            # Recipient must explicitly have access to the basket, never expose it via task assignment.
            basket_access(db,d.basket_id,d.assigned_to)
            if d.assigned_to==user['id']:raise HTTPException(422,'Elige otra persona o deja el recado abierto')
        if d.store_id is not None:existing(db,'stores',d.store_id)
        if d.due_on:
            try:date.fromisoformat(d.due_on)
            except ValueError:raise HTTPException(422,'Fecha inválida')
        r=db.execute('''INSERT INTO family_tasks(basket_id,created_by,assigned_to,title,note,due_on,store_id,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,'open',?,?)''',(d.basket_id,user['id'],d.assigned_to,
            d.title.strip(),d.note.strip(),d.due_on,d.store_id,now(),now()))
        return {'id':r.lastrowid,'status':'open','info':'Sin reserva ni envío al supermercado'}

class FamilyTaskStatus(BaseModel):
    status:str=Field(pattern='^(accepted|done|open|cancelled)$')

@app.patch('/api/family/tasks/{task_id}')
def family_task_update(task_id:int,d:FamilyTaskStatus,user=Depends(auth)):
    with connect() as db:
        task=one(db,'SELECT * FROM family_tasks WHERE id=?',(task_id,))
        if not task:raise HTTPException(404,'Recado no encontrado')
        basket_access(db,task['basket_id'],user['id'])
        if d.status=='cancelled':
            if task['created_by']!=user['id']:raise HTTPException(403,'Solo quien creó el recado puede cancelarlo')
        elif d.status=='accepted':
            if task['status']!='open' or task['assigned_to'] not in (None,user['id']):
                raise HTTPException(409,'El recado no está disponible')
        elif d.status=='done':
            if task['status']!='accepted' or task['assigned_to']!=user['id']:
                raise HTTPException(403,'Solo quien aceptó el recado puede completarlo')
        elif d.status=='open':
            if task['created_by']!=user['id'] or task['status'] in ('done','cancelled'):
                raise HTTPException(403,'Solo la persona creadora puede reabrir este recado')
        assignee=user['id'] if d.status=='accepted' else None if d.status=='open' else task['assigned_to']
        cur=db.execute('UPDATE family_tasks SET status=?,assigned_to=?,updated_at=? WHERE id=? AND status=?',
                       (d.status,assignee,now(),task_id,task['status']))
        if cur.rowcount!=1:raise HTTPException(409,'Recado modificado por otra persona, actualiza')
    return {'ok':True,'status':d.status}

# Real-time family basket updates over authenticated HTTPS (best-effort while open).
# Other pages use regular refresh; no background notifications claimed.
def _basket_fingerprint(db,bid):
    lines=[]
    for table,fields in [('basket_items','product_id,quantity,checked'),
                         ('basket_free_items','id,title,quantity,checked'),
                         ('basket_members','user_id,role')]:
        rows=many(db,f'SELECT {fields} FROM {table} WHERE basket_id=? ORDER BY 1',(bid,))
        lines.append(rows)
    basket=one(db,'SELECT title,kind,updated_at FROM baskets WHERE id=?',(bid,))
    lines.append(basket)
    return hashlib.sha256(json.dumps(lines,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:18]

@app.get('/api/baskets/{bid}/events')
async def basket_stream(bid:int,req:Request,user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'])

    async def generate():
        previous=None
        for tick in range(600):  # browsers reconnect after ~20 min
            if await req.is_disconnected():break
            with connect() as db:
                try:
                    basket_access(db,bid,user['id'])
                    digest=_basket_fingerprint(db,bid)
                except HTTPException:
                    yield 'event: revoked\ndata: {}\n\n'
                    break
            if previous is None:
                previous=digest
                yield ': connected\n\n'
            elif digest!=previous:
                previous=digest
                yield 'event: updated\ndata: {"changed":true}\n\n'
            elif tick%7==0:
                yield ': ping\n\n'
            await asyncio.sleep(2)
    return StreamingResponse(generate(),media_type='text/event-stream',headers={
        'Cache-Control':'no-store, no-transform', 'X-Accel-Buffering':'no'})


# SHOPPER 10 — Small, manually verified chain-web sample. It does not state
# that a particular physical branch carries any item, nor sell inventory.
_RETAIL_DATA_PATH=ROOT/'data'/'retail_official_snapshot_2026-11-23.json'
_RETAIL_CACHE=json.loads(_RETAIL_DATA_PATH.read_text('utf-8'))

@app.get('/api/retail/catalog')
def retail_catalog(chain:str='',q:str='',category:str='',store_id:int|None=None):
    if len(q)>100 or len(chain)>60 or len(category)>60:
        raise HTTPException(400,'Búsqueda demasiado larga')
    store=None
    if store_id is not None:
        with connect() as db:
            store=one(db,'SELECT id,name,chain,address FROM stores WHERE id=?',(store_id,))
        if store is None:raise HTTPException(404,'Tienda no encontrada')
        chain=store['chain']
    needle=q.strip().casefold()
    with connect() as db:
        mapping={r['listing_id']:r['product_id'] for r in many(db,'SELECT listing_id,product_id FROM retail_catalog_links')}
    rows=[]
    for item in _RETAIL_CACHE['items']:
        if chain and item['chain'].casefold()!=chain.casefold():continue
        if category and item['category'].casefold()!=category.casefold():continue
        if needle and needle not in ' '.join((item['name'],item['brand'],item['category'])).casefold():continue
        rows.append({**item,'product_id':mapping.get(item['id'])})
    return {'items':rows,'total':len(rows),'snapshot_date':_RETAIL_CACHE['capture_date'],
            'store':store,'chains':sorted(set(x['chain'] for x in _RETAIL_CACHE['items'])),
            'scope':'Cadena online, NO inventario de tienda física',
            'notice':'Muestra editorial de fichas web reales, no catálogo completo; precios observados el 23/11/2026, sin garantía de vigencia. Nunca se afirma disponibilidad en sucursales concretas.'}


@app.get('/api/places/{place_id}/retail')
def place_retail(place_id:int, q:str='',category:str='',user=Depends(auth)):
    if len(q)>100 or len(category)>60:raise HTTPException(400,'Búsqueda demasiado larga')
    with connect() as db:
        place=own_place(db,place_id,user['id'])
        stores=many(db,'''SELECT s.id,s.name,s.chain,s.address FROM place_stores ps
                     JOIN stores s ON s.id=ps.store_id WHERE ps.place_id=? ORDER BY s.chain,s.name''',(place_id,))
    chains={st['chain'].casefold() for st in stores}
    items=[dict(x) for x in _RETAIL_CACHE['items']
           if x['chain'].casefold() in chains and q.casefold().strip() in
              ' '.join((x['name'],x['brand'],x['category'])).casefold()
           and (not category or x['category'].casefold()==category.casefold())]
    with connect() as db:
        links={r['listing_id']:r['product_id'] for r in many(db,'SELECT listing_id,product_id FROM retail_catalog_links')}
    for item in items:item['product_id']=links.get(item['id'])
    return {'place':{'id':place['id'],'name':place['name']},'stores':stores,'items':items,'total':len(items),
      'capture_date':_RETAIL_CACHE['capture_date'],'data_scope':'Precios web por CADENA, no inventario ni stock de sucursal',
      'note':'Las redes filtran cadenas comerciales, pero no validan presencia de cada SKU en la tienda guardada.'}

@app.get('/api/baskets/{bid}/shopping-context')
def basket_shopping_context(bid:int,user=Depends(auth)):
    with connect() as db:
        b=basket_access(db,bid,user['id'])
        owner=b['owner_id']
        store_rows=many(db,'''SELECT s.id,s.name,s.chain,s.address FROM basket_store_preferences bp
                      JOIN stores s ON s.id=bp.store_id WHERE bp.basket_id=? ORDER BY s.chain,s.name''',(bid,))
        if b['place_id'] and not store_rows:
            store_rows=many(db,'''SELECT s.id,s.name,s.chain,s.address FROM place_stores ps
                 JOIN stores s ON s.id=ps.store_id WHERE ps.place_id=? ORDER BY s.chain,s.name''',(b['place_id'],))
        place=one(db,'SELECT id,name FROM places WHERE id=? AND user_id=?',(b['place_id'],owner)) if b['place_id'] else None
        basket_items=many(db,'''SELECT p.name,bi.product_id,bi.quantity FROM basket_items bi
              JOIN products p ON p.id=bi.product_id WHERE bi.basket_id=?''',(bid,))
        free=many(db,'SELECT title name,quantity FROM basket_free_items WHERE basket_id=?',(bid,))
        linked={r['product_id']:r['listing_id'] for r in many(db,'SELECT product_id,listing_id FROM retail_catalog_links')}
    chains=sorted({st['chain'] for st in store_rows})
    cards=[]
    for chain in chains:
        lookup={p['id']:p for p in _RETAIL_CACHE['items'] if p['chain'].casefold()==chain.casefold()}
        present=[(r,lookup[linked[r['product_id']]]) for r in basket_items if linked.get(r['product_id']) in lookup]
        coverage=len(present)
        missing=len(basket_items)+len(free)-coverage
        subtotal=sum(round(float(r['quantity'])*p['price_cents']) for r,p in present)
        cards.append({'chain':chain,'coverage':coverage,'line_count':len(basket_items)+len(free),
               'missing':missing,'partial_subtotal_cents':subtotal if coverage else None,
               'comparable_total_cents':subtotal if missing==0 and coverage>0 else None})
    return {'basket_id':bid,'place':place,'stores':store_rows,'chains':cards,
        'capture_date':_RETAIL_CACHE['capture_date'], 'products_total':len(basket_items)+len(free),
        'scope':'Datos históricos web de cadena, NO disponibilidad, descuento en tiempo real ni promesa de ahorro',
        'warning':'Si faltan artículos no se publican totales comparables. No se atribuyen fichas web a una sucursal.'}

_OFF_SEARCH_CACHE={}
_OFF_SEARCH_LOCK=Lock()
_OFF_SEARCH_TIMES=deque()

def off_agent():
    value=os.getenv('SHOPPER_OFF_USER_AGENT','').strip()
    if not re.fullmatch(r'.{2,90}/[0-9.]+ \([^\s()@]+@[^\s()@]+\)',value):
        raise HTTPException(503,'El administrador debe configurar SHOPPER_OFF_USER_AGENT para activar Open Food Facts')
    return value

@app.get('/api/food/search')
def food_search(q:str=Query(min_length=2,max_length=70),user=Depends(auth)):
    q=q.strip().lower()
    if len(q)<2:raise HTTPException(400,'Escribe al menos dos caracteres')
    agent=off_agent()
    t=time.monotonic()
    with _OFF_SEARCH_LOCK:
        cached=_OFF_SEARCH_CACHE.get(q)
        if cached and cached[0]>t-900:return cached[1]
        while _OFF_SEARCH_TIMES and _OFF_SEARCH_TIMES[0]<t-60:_OFF_SEARCH_TIMES.popleft()
        if len(_OFF_SEARCH_TIMES)>=8:raise HTTPException(429,'Demasiadas búsquedas externas; inténtalo en un minuto')
        _OFF_SEARCH_TIMES.append(t)
    from urllib.parse import urlencode
    params=urlencode({'search_terms':q,'page_size':18,'fields':'code,product_name,product_name_es,brands,quantity,image_front_small_url,nutriscore_grade,countries_tags,ingredients_text_es','sort_by':'unique_scans_n'})
    # Without declaring a shop, because OFF product data is not a shop inventory.
    url='https://world.openfoodfacts.org/api/v2/search?'+params
    req=urllib.request.Request(url,headers={'User-Agent':agent,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as resp:
            raw=json.loads(resp.read(2_000_000).decode('utf-8'))
    except Exception as exc:
        raise HTTPException(502,'No se ha podido consultar Open Food Facts en este momento') from exc
    results=[]
    for p in (raw.get('products') or []):
        if not isinstance(p,dict):continue
        code=str(p.get('code') or '')
        name=str(p.get('product_name_es') or p.get('product_name') or '').strip()
        if not code or not name or not gtin_valid(code):continue
        img=str(p.get('image_front_small_url') or '')
        if not img.startswith('https://images.openfoodfacts.org/'):
            img=None
        results.append({'code':code,'name':name[:120],'brand':str(p.get('brands') or '')[:80],
          'format':str(p.get('quantity') or '')[:45],'image':img,'nutriscore':str(p.get('nutriscore_grade') or '')[:1],
          'source':'Open Food Facts · ODbL','product_url':f'https://world.openfoodfacts.org/product/{code}'})
    answer={'items':results[:18],'total':len(results),'source':'Open Food Facts (ODbL)',
            'notice':'Información colaborativa del producto, no precio ni disponibilidad en ninguna tienda.'}
    with _OFF_SEARCH_LOCK:
        if len(_OFF_SEARCH_CACHE)>250:_OFF_SEARCH_CACHE.clear()
        _OFF_SEARCH_CACHE[q]=(t,answer)
    return answer

class OFFImport(BaseModel):
    code:str=Field(min_length=8,max_length=14)

@app.post('/api/food/import')
def food_import(d:OFFImport,user=Depends(auth)):
    if not gtin_valid(d.code):raise HTTPException(400,'Código de barras inválido')
    with connect() as db:
        old=one(db,'SELECT id FROM products WHERE gtin=?',(d.code,))
        if old:return {'id':old['id'],'already_present':True}
    info=off_lookup(d.code,user) # User-triggered and externally rate-limited.
    if not info['found'] or not info.get('name'):
        raise HTTPException(404,'No hay datos suficientes de este producto en Open Food Facts')
    with connect() as db:
        old=one(db,'SELECT id FROM products WHERE gtin=?',(d.code,))
        if old:return {'id':old['id'],'already_present':True}
        try:
            cur=db.execute("""INSERT INTO products(name,gtin,category,format_text,ingredients,allergens,source_url,source_status,added_by,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (info['name'],d.code,'Producto Open Food Facts',info.get('quantity') or '',info.get('ingredients'),
                info.get('allergens'),info['url'],'Open Food Facts (ODbL), sin verificación de tienda ni precio',user['id'],now()))
            return {'id':cur.lastrowid,'already_present':False}
        except sqlite3.IntegrityError:
            found=one(db,'SELECT id FROM products WHERE gtin=?',(d.code,))
            return {'id':found['id'],'already_present':True}

@app.get('/api/retail/baskets/{bid}/summary')
def retail_basket_summary(bid:int,chain:str='DIA',user=Depends(auth)):
    with connect() as db:
        basket_access(db,bid,user['id'])
        rows=many(db,'SELECT product_id,quantity FROM basket_items WHERE basket_id=?',(bid,))
        free=one(db,'SELECT COUNT(*) as n FROM basket_free_items WHERE basket_id=?',(bid,))['n']
        mapped={r['product_id']:r['listing_id'] for r in many(db,'SELECT product_id,listing_id FROM retail_catalog_links')}
    skus={x['id']:x for x in _RETAIL_CACHE['items'] if x['chain'].lower()==chain.lower()}
    known=[];missing=[]
    for row in rows:
        listing=skus.get(mapped.get(row['product_id']))
        if listing:
            known.append({'name':listing['name'],'quantity':row['quantity'],'price_cents':listing['price_cents'],
                          'subtotal_cents':round(listing['price_cents']*row['quantity'])})
        else:missing.append(row['product_id'])
    full=len(missing)==0 and free==0 and len(rows)>0
    return {'chain':chain,'complete':full,'known_count':len(known),'total_items':len(rows)+free,
       'missing_count':len(missing)+free,'known_subtotal_cents':sum(x['subtotal_cents'] for x in known),
       'estimated_total_cents':sum(x['subtotal_cents'] for x in known) if full else None,
       'lines':known,'notice':'Subtotal según precios web de 23/11/2026. NO precio confirmado hoy ni disponibilidad en tienda física. No enviar pedido.'}


# V11: small trust-circle mutual aid; NOT a public map of vulnerable people.
def help_requests_for(db,uid):
    return many(db,"""SELECT h.id,h.creator_id,h.basket_id,h.area_label,h.note,h.needed_on,h.status,
             h.helper_id,h.created_at,u.display_name creator_name,hu.display_name helper_name,
             CASE WHEN b.owner_id=? OR EXISTS(SELECT 1 FROM basket_members bm WHERE bm.basket_id=b.id AND bm.user_id=?)
                  THEN b.title ELSE NULL END basket_title
      FROM trusted_help_requests h JOIN users u ON u.id=h.creator_id
      LEFT JOIN users hu ON hu.id=h.helper_id LEFT JOIN baskets b ON b.id=h.basket_id
      WHERE h.creator_id=? OR h.helper_id=? OR EXISTS (
        SELECT 1 FROM friendships f WHERE (f.u_low=? AND f.u_high=h.creator_id)
        OR (f.u_high=? AND f.u_low=h.creator_id))
      ORDER BY h.created_at DESC,h.id DESC LIMIT 70""",(uid,uid,uid,uid,uid,uid))

class TrustHelpCreate(BaseModel):
    area_label:str=Field(min_length=3,max_length=70)
    note:str=Field(min_length=4,max_length=240)
    basket_id:int|None=None
    needed_on:date|None=None

@app.get('/api/circle/help')
def circle_help_list(user=Depends(auth)):
    with connect() as db:return {'items':help_requests_for(db,user['id']),
       'privacy':'Solo visible para amistades aceptadas y personas implicadas. Nunca comparte coordenadas ni domicilio.'}

@app.post('/api/circle/help')
def circle_help_create(d:TrustHelpCreate,user=Depends(auth)):
    if re.search(r'\b(?:calle|avenida|avda\.?|piso|portal|puerta|n[úu]mero)\b',d.area_label,re.I) or re.search(r'\b(?:calle|avenida|avda\.?|piso|portal|puerta)\b',d.note,re.I):
        raise HTTPException(400,'Indica solo una zona general, no la dirección ni el piso')
    with connect() as db:
        if d.basket_id is not None:
            b=basket_access(db,d.basket_id,user['id'])
            if b['owner_id']!=user['id']:
                raise HTTPException(400,'Para pedir ayuda vincula una cesta de tu propiedad')
        c=db.execute('''INSERT INTO trusted_help_requests(creator_id,basket_id,area_label,note,needed_on,status,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?)''',(user['id'],d.basket_id,d.area_label.strip(),d.note.strip(),d.needed_on.isoformat() if d.needed_on else None,'open',now(),now()))
        return {'id':c.lastrowid,'status':'open','note':'Solo tus contactos aceptados pueden ver esta solicitud'}

class HelpStatus(BaseModel):
    action:str

@app.post('/api/circle/help/{hid}/action')
def circle_help_action(hid:int,d:HelpStatus,user=Depends(auth)):
    if d.action not in ('accept','done','cancel'):raise HTTPException(400,'Acción incorrecta')
    uid=user['id']
    with connect() as db:
        req=existing(db,'trusted_help_requests',hid)
        if d.action=='accept':
            if req['creator_id']==uid:raise HTTPException(400,'No puedes aceptar tu propia solicitud')
            friend=one(db,'SELECT 1 yes FROM friendships WHERE (u_low=? AND u_high=?) OR (u_low=? AND u_high=?)',
                     (min(uid,req['creator_id']),max(uid,req['creator_id']),min(uid,req['creator_id']),max(uid,req['creator_id'])))
            if not friend:raise HTTPException(403,'Esta ayuda está limitada a contactos aceptados')
            cur=db.execute("UPDATE trusted_help_requests SET status='accepted',helper_id=?,updated_at=? WHERE id=? AND status='open'",
                           (uid,now(),hid))
            if cur.rowcount!=1:raise HTTPException(409,'La solicitud ya no está disponible')
        elif d.action=='done':
            if uid not in (req['creator_id'],req['helper_id']) or req['status']!='accepted':
                raise HTTPException(403,'Solo quienes participan pueden darla por completada')
            db.execute("UPDATE trusted_help_requests SET status='done',updated_at=? WHERE id=?",(now(),hid))
        elif d.action=='cancel':
            if req['creator_id']!=uid or req['status'] not in ('open','accepted'):
                raise HTTPException(403,'Solo quien publicó puede cancelar una solicitud activa')
            db.execute("UPDATE trusted_help_requests SET status='cancelled',updated_at=? WHERE id=?",(now(),hid))
    return {'ok':True}

# V12 extensions: keep historical API paths and migrations intact.
from v12api import install as _install_v12
_install_v12(app, auth)

# SHOPPER 13: encrypted loyalty and recipe-to-basket
from v13api import install as _install_v13
_install_v13(app, auth)
