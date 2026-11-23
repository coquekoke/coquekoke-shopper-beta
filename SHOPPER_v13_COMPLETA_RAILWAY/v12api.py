"""SHOPPER v12: geospatial discovery, purchase-to-pantry, local social feed, trusted errands.
All commercial integrations are explicitly out of scope; OpenStreetMap Overpass is PILOT-ONLY.
"""
from __future__ import annotations
import json, math, os, re, sqlite3, time, threading, urllib.request, urllib.parse, datetime
from datetime import datetime as dt, timezone, timedelta
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException, Query
from db import connect, many, one, now

OSM_URL='https://overpass-api.de/api/interpreter'
_osm_lock=threading.Lock()
_osm_last={}

DDL='''
CREATE TABLE IF NOT EXISTS v12_store_osm(
 osm_id TEXT PRIMARY KEY, store_id INTEGER NOT NULL REFERENCES stores(id), imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v12_prefs(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 auto_pantry INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS v12_purchases(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 basket_id INTEGER REFERENCES baskets(id) ON DELETE SET NULL, source TEXT NOT NULL,
 store_ids_json TEXT NOT NULL DEFAULT '[]', basket_title TEXT NOT NULL DEFAULT '',
 paid_cents INTEGER NOT NULL, minutes_spent INTEGER, items_json TEXT NOT NULL,
 received_at TEXT, pantry_added_at TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS v12_purchases_user ON v12_purchases(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS v12_pantry_transfer(
 purchase_id INTEGER NOT NULL REFERENCES v12_purchases(id), item_index INTEGER NOT NULL,
 pantry_id INTEGER NOT NULL REFERENCES pantry(id),PRIMARY KEY(purchase_id,item_index));
CREATE TABLE IF NOT EXISTS v12_social_posts(
 id INTEGER PRIMARY KEY AUTOINCREMENT,author_id INTEGER NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL, store_id INTEGER REFERENCES stores(id), product_id INTEGER REFERENCES products(id),
 visibility TEXT NOT NULL CHECK(visibility IN ('community','friends')),
 title TEXT NOT NULL,body TEXT NOT NULL,price_cents INTEGER, observed_at TEXT,
 created_at TEXT NOT NULL, expires_at TEXT, status TEXT NOT NULL DEFAULT 'visible');
CREATE INDEX IF NOT EXISTS v12_social_time ON v12_social_posts(created_at DESC);
CREATE TABLE IF NOT EXISTS v12_social_reactions(
 post_id INTEGER NOT NULL REFERENCES v12_social_posts(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL,
 PRIMARY KEY(post_id,user_id));
CREATE TABLE IF NOT EXISTS v12_social_comments(
 id INTEGER PRIMARY KEY AUTOINCREMENT,post_id INTEGER NOT NULL REFERENCES v12_social_posts(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES users(id),body TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v12_social_flags(
 post_id INTEGER NOT NULL REFERENCES v12_social_posts(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id),reason TEXT NOT NULL,PRIMARY KEY(post_id,user_id));
CREATE TABLE IF NOT EXISTS v12_neighbor_offers(
 id INTEGER PRIMARY KEY AUTOINCREMENT,creator_id INTEGER NOT NULL REFERENCES users(id),
 store_id INTEGER REFERENCES stores(id),note TEXT NOT NULL,area_label TEXT NOT NULL,
 until_at TEXT NOT NULL,accepted_by INTEGER REFERENCES users(id),status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS v12_neighbor_time ON v12_neighbor_offers(until_at DESC);
'''

def migrate():
    with connect() as db:db.executescript(DDL)

def distance_km(lat,lon,a,b):
    lat1,lat2=map(math.radians,(lat,a)); dlat=lat2-lat1;dlon=math.radians(b-lon)
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return round(6371*2*math.asin(min(1,math.sqrt(h))),2)

def center_madrid(lat,lon):
    if not (39.8<=lat<=41.3 and -4.65<=lon<=-3.05):
        raise HTTPException(400,'Descubrimiento de tiendas limitado al área de Madrid en el piloto.')

def store_chain(tags):
    raw=(tags.get('brand') or tags.get('operator') or tags.get('name') or 'Independiente').strip()
    known=['DIA','Mercadona','Carrefour','Lidl','ALDI','Alcampo','Ahorramás','AhorraMás','Hipercor','El Corte Inglés','Supercor','BM','Eroski','La Sirena','Hiber','Sánchez Romero','Covirán','Spar','Consum','BonÀrea','Makro','Froiz','Unide','Charter']
    for c in known:
        if c.casefold() in raw.casefold():return 'Ahorramás' if c=='AhorraMás' else c
    return raw[:70]

def addr_from_osm(tags):
    if tags.get('addr:street'):
        return ' '.join(x for x in [tags['addr:street'],tags.get('addr:housenumber','')] if x).strip()+', '+(tags.get('addr:city') or 'Madrid')+', España'
    if tags.get('addr:place'):
        return tags['addr:place']+', '+(tags.get('addr:city') or 'Madrid')+', España'
    return 'Dirección incompleta · '+(tags.get('addr:city') or 'Comunidad de Madrid')

def import_overpass(db,elements,cap=900):
    added=0; updated=0
    for e in elements[:cap]:
        tags=e.get('tags') or {}; osm_ref=f"{e.get('type')}/{e.get('id')}"
        if tags.get('shop') not in ('supermarket','convenience','grocery','frozen_food') or not e.get('id'):continue
        coords=e.get('center') or e
        lat=coords.get('lat');lon=coords.get('lon')
        if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)):continue
        if not(39.8<=lat<=41.3 and -4.65<=lon<=-3.05):continue
        name=str(tags.get('name') or tags.get('brand') or 'Tienda de alimentación').strip()[:100]
        chain=store_chain(tags);addr=addr_from_osm(tags)[:230]
        # An OSM feature without a street is still a distinct physical shop.
        # Avoid collapsing hundreds of unnamed shops onto one UNIQUE(name,address) record.
        if addr.startswith('Dirección incompleta'):
            addr=(addr[:155]+' · '+osm_ref)[:230]
        known=one(db,'SELECT store_id FROM v12_store_osm WHERE osm_id=?',(osm_ref,))
        if known:
            db.execute('UPDATE stores SET lat=?,lon=?,address=CASE WHEN source_type=? THEN ? ELSE address END WHERE id=?',
                       (lat,lon,'openstreetmap',addr,known['store_id']))
            updated+=1;continue
        # Avoid duplicates where existing address is known and exactly matches.
        pre=one(db,'SELECT id FROM stores WHERE lower(name)=lower(?) AND lower(address)=lower(?)',(name,addr))
        if pre: sid=pre['id']
        else:
            try:
                sid=db.execute('''INSERT INTO stores(name,chain,address,municipality,region,lat,lon,source_type,source_url,verified_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?)''',
                      (name,chain,addr,(tags.get('addr:city') or 'Madrid')[:80],'Madrid',lat,lon,'openstreetmap',
                       'https://www.openstreetmap.org/'+osm_ref,now())).lastrowid
                added+=1
            except sqlite3.IntegrityError:continue
        db.execute('INSERT OR IGNORE INTO v12_store_osm(osm_id,store_id,imported_at) VALUES (?,?,?)',(osm_ref,sid,now()))
    return {'added':added,'updated':updated}

def friend(db,me,other):
    if me==other:return False
    return bool(one(db,'SELECT 1 FROM friendships WHERE u_low=? AND u_high=?',(min(me,other),max(me,other))))

def list_nearby(db,lat,lon,radius,query,chain,limit):
    # Pre-filter bounding box for efficiency, then Haversine. No raw coordinates logged.
    dr=radius/110.0; dl=radius/(111*max(.1,math.cos(math.radians(lat))))
    sql='SELECT * FROM stores WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?'
    rows=many(db,sql,(lat-dr,lat+dr,lon-dl,lon+dl))
    q=query.casefold().strip(); ch=chain.casefold().strip()
    data=[]
    for s in rows:
        if q and q not in (s['name']+' '+s['chain']+' '+s['address']).casefold():continue
        if ch and ch!=s['chain'].casefold():continue
        s['distance_km']=distance_km(lat,lon,s['lat'],s['lon'])
        if s['distance_km']<=radius:data.append(s)
    return sorted(data,key=lambda s:(s['distance_km'],s['name']))[:limit]

class PlaceGeo(BaseModel):
    lat:float=Field(ge=-90,le=90)
    lon:float=Field(ge=-180,le=180)

class PurchaseExtra(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    quantity:float=Field(gt=0,le=9999)
    unit:Literal['ud','kg','g','l','ml','pack']='ud'

class PurchaseCreate(BaseModel):
    basket_id:int|None=None
    store_ids:list[int]=Field(default_factory=list,max_length=12)
    paid_cents:int=Field(ge=0,le=10_000_000)
    minutes_spent:int|None=Field(default=None,ge=0,le=1440)
    extras:list[PurchaseExtra]=Field(default_factory=list,max_length=80)
    received:bool=False
    pantry_mode:Literal['default','add','skip']='default'
    checked_only:bool=False

class ReceivePurchase(BaseModel):
    pantry_mode:Literal['default','add','skip']='default'

class OptIn(BaseModel):
    auto_pantry:bool

class SocialCreate(BaseModel):
    kind:Literal['oferta','repuesto','agotado','nuevo','retirado','valoracion','receta','consejo']
    title:str=Field(min_length=3,max_length=100)
    body:str=Field(min_length=4,max_length=800)
    visibility:Literal['community','friends']='community'
    store_id:int|None=None
    product_id:int|None=None
    price_cents:int|None=Field(default=None,ge=1,le=10_000_000)

class React(BaseModel):
    kind:Literal['util','interesante','guardado','dudo','none']

class Comment(BaseModel):
    body:str=Field(min_length=2,max_length=400)

class Flag(BaseModel):
    reason:Literal['spam','falso','abusivo','datos_personales']

class NeighborOffer(BaseModel):
    store_id:int|None=None
    area_label:str=Field(min_length=3,max_length=75)
    note:str=Field(min_length=8,max_length=260)
    minutes_available:int=Field(ge=15,le=180)

class NeighborAccept(BaseModel):
    action:Literal['accept','cancel','complete']


def transfer_to_pantry(db,purchase_id,user_id,mode):
    purchase=one(db,'SELECT * FROM v12_purchases WHERE id=? AND user_id=?',(purchase_id,user_id))
    if not purchase:raise HTTPException(404,'Compra no encontrada')
    if not purchase['received_at']:raise HTTPException(409,'Confirma recepción antes de pasar artículos a la despensa')
    saved=one(db,'SELECT auto_pantry FROM v12_prefs WHERE user_id=?',(user_id,))
    enabled=(mode=='add') or (mode=='default' and bool(saved and saved['auto_pantry']))
    if not enabled:return 0
    if purchase['pantry_added_at']:return 0
    count=0
    for index,item in enumerate(json.loads(purchase['items_json'])):
        if one(db,'SELECT 1 FROM v12_pantry_transfer WHERE purchase_id=? AND item_index=?',(purchase_id,index)):
            continue
        name=str(item.get('name') or '').strip()
        if not name:continue
        qty=float(item.get('quantity') or 1)
        unit=item.get('unit') or 'ud'
        pid=item.get('product_id')
        c=db.execute('''INSERT INTO pantry(user_id,product_id,custom_name,quantity,unit,created_at)
                        VALUES(?,?,?,?,?,?)''',
                    (user_id,pid,None if pid else name,qty,unit,now()))
        db.execute('INSERT INTO v12_pantry_transfer(purchase_id,item_index,pantry_id) VALUES(?,?,?)',
                   (purchase_id,index,c.lastrowid));count+=1
    db.execute('UPDATE v12_purchases SET pantry_added_at=? WHERE id=?',(now(),purchase_id))
    return count


def install(app, auth):
    """Install after original routes and auth middleware have been configured."""
    migrate()

    @app.get('/api/v12/stores/nearby')
    def stores_nearby(lat:float=Query(40.4168,ge=-90,le=90),lon:float=Query(-3.7038,ge=-180,le=180),
                      radius_km:float=Query(8,ge=.2,le=30),q:str=Query('',max_length=80),chain:str=Query('',max_length=60),
                      limit:int=Query(160,ge=1,le=500)):
        center_madrid(lat,lon)
        with connect() as db:
            data=list_nearby(db,lat,lon,radius_km,q,chain,limit)
        return {'items':data,'count':len(data),'location_used':'Coordenadas enviadas voluntariamente para proximidad',
                'complete':False,'source_notice':'Directorio comunitario/OSM; no refleja stock ni horarios confirmados'}

    @app.post('/api/v12/stores/discover')
    def discover(d:PlaceGeo, radius_km:float=Query(3,ge=.5,le=8),user=Depends(auth)):
        center_madrid(d.lat,d.lon)
        if os.getenv('SHOPPER_OSM_PILOT','0')!='1':
            raise HTTPException(503,'Consulta OSM desactivada. El administrador debe importar un extracto licenciado o activar explícitamente SHOPPER_OSM_PILOT=1 para una beta pequeña.')
        key=(user['id'])
        with _osm_lock:
            t=time.monotonic()
            if t-_osm_last.get(key,0)<100:
                raise HTTPException(429,'Consulta reciente. Usa el directorio guardado o vuelve a intentarlo en unos minutos.')
            _osm_last[key]=t
        # Overpass reads from OSM. Pilot opt-in only; not an SLA or commercial live feed.
        radius=int(radius_km*1000)
        qry=f'''[out:json][timeout:22];(nwr["shop"~"^(supermarket|convenience|grocery|frozen_food)$"](around:{radius},{d.lat:.5f},{d.lon:.5f}););out center 900;'''
        req=urllib.request.Request(OSM_URL,data=urllib.parse.urlencode({'data':qry}).encode(),headers={'User-Agent':('SHOPPER-Private-Pilot/12.0 '+os.getenv('SHOPPER_CONTACT_EMAIL',''))[:120], 'Content-Type':'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(req,timeout=28) as res:
                payload=json.loads(res.read(2_000_000))
        except Exception:
            raise HTTPException(503,'El directorio OSM no respondió. Reintenta más tarde o utiliza los supermercados guardados.')
        with connect() as db:counts=import_overpass(db,payload.get('elements',[]))
        return {'ok':True,**counts,'data_source':'OpenStreetMap contributors · ODbL','cached_in_local_directory':True,
                'notice':'Descubrimiento puntual para beta privada; no prueba que el local siga abierto'}

    @app.patch('/api/v12/places/{place_id}/coordinates')
    def place_coordinates(place_id:int,d:PlaceGeo,user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT id FROM places WHERE id=? AND user_id=?',(place_id,user['id']))
            if not p:raise HTTPException(403,'Lugar no autorizado')
            db.execute('UPDATE places SET lat=?,lon=? WHERE id=?',(d.lat,d.lon,place_id))
        return {'ok':True,'privacy':'Coordenadas privadas de este usuario'}

    @app.get('/api/v12/pantry/settings')
    def settings(user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT auto_pantry FROM v12_prefs WHERE user_id=?',(user['id'],))
        return {'auto_pantry':bool(p and p['auto_pantry'])}

    @app.put('/api/v12/pantry/settings')
    def set_settings(d:OptIn,user=Depends(auth)):
        with connect() as db:db.execute('INSERT INTO v12_prefs(user_id,auto_pantry) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET auto_pantry=excluded.auto_pantry',(user['id'],int(d.auto_pantry)))
        return {'auto_pantry':d.auto_pantry}

    def owned_basket(db,bid,uid):
        # A member of an invited shared basket can log THEIR OWN purchase; the entry
        # is private to the buyer and never changes the shared basket itself.
        b=one(db,'SELECT b.* FROM baskets b LEFT JOIN basket_members bm ON bm.basket_id=b.id AND bm.user_id=? WHERE b.id=? AND (b.owner_id=? OR bm.user_id=?)',(uid,bid,uid,uid))
        if not b:raise HTTPException(403,'No tienes acceso a esta cesta')
        return b

    @app.get('/api/v12/purchases')
    def purchases(user=Depends(auth)):
        with connect() as db:return {'items':many(db,'SELECT id,basket_title,paid_cents,minutes_spent,created_at,received_at,pantry_added_at,source,store_ids_json FROM v12_purchases WHERE user_id=? ORDER BY id DESC LIMIT 80',(user['id'],))}

    @app.post('/api/v12/purchases')
    def new_purchase(d:PurchaseCreate,user=Depends(auth)):
        with connect() as db:
            title='Compra personal'; items=[]
            if d.basket_id is not None:
                b=owned_basket(db,d.basket_id,user['id']);title=b['title']
                for i in many(db,'''SELECT i.product_id,p.name,i.quantity,i.checked FROM basket_items i JOIN products p ON p.id=i.product_id WHERE i.basket_id=?''',(d.basket_id,)):
                    if not d.checked_only or i['checked']:items.append({'product_id':i['product_id'],'name':i['name'],'quantity':i['quantity'],'unit':'ud'})
                for i in many(db,'SELECT title name,quantity,checked FROM basket_free_items WHERE basket_id=?',(d.basket_id,)):
                    if not d.checked_only or i['checked']:items.append({'product_id':None,'name':i['name'],'quantity':i['quantity'],'unit':'ud'})
            for extra in d.extras:items.append({'product_id':None,'name':extra.name.strip(),'quantity':extra.quantity,'unit':extra.unit})
            if not items:raise HTTPException(400,'Añade productos a la cesta o algún producto extra')
            if len(items)>250:raise HTTPException(400,'Demasiados productos para una compra')
            for sid in set(d.store_ids):
                if not one(db,'SELECT id FROM stores WHERE id=?',(sid,)):raise HTTPException(400,'Tienda no encontrada')
            dateval=now() if d.received else None
            c=db.execute('''INSERT INTO v12_purchases(user_id,basket_id,source,store_ids_json,basket_title,paid_cents,minutes_spent,items_json,received_at,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?)''',
                      (user['id'],d.basket_id,'manual',json.dumps(sorted(set(d.store_ids))),title,d.paid_cents,d.minutes_spent,json.dumps(items,ensure_ascii=False),dateval,now()))
            count=transfer_to_pantry(db,c.lastrowid,user['id'],d.pantry_mode) if d.received else 0
            return {'id':c.lastrowid,'status':'received' if d.received else 'awaiting_confirmation','pantry_added':count,
                    'note':'Compra declarada por el usuario; importe y stock no verificados por la tienda'}

    @app.post('/api/v12/purchases/{purchase_id}/receive')
    def mark_received(purchase_id:int,d:ReceivePurchase,user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT * FROM v12_purchases WHERE id=? AND user_id=?',(purchase_id,user['id']))
            if not p:raise HTTPException(404,'Compra no encontrada')
            if not p['received_at']:db.execute('UPDATE v12_purchases SET received_at=? WHERE id=?',(now(),purchase_id))
            count=transfer_to_pantry(db,purchase_id,user['id'],d.pantry_mode)
            return {'ok':True,'already_received':bool(p['received_at']),'pantry_added':count}

    def can_see(db,post,uid):
        return post['visibility']=='community' or post['author_id']==uid or friend(db,post['author_id'],uid)

    @app.get('/api/v12/social')
    def feed(kind:str=Query('',max_length=20),store_id:int|None=None,limit:int=Query(80,ge=1,le=150),user=Depends(auth)):
        with connect() as db:
            rows=many(db,'''SELECT p.*,u.display_name author_name,s.name store_name,pr.name product_name,
                   (SELECT COUNT(*) FROM v12_social_comments cm WHERE cm.post_id=p.id) comments,
                   (SELECT COUNT(*) FROM v12_social_reactions r WHERE r.post_id=p.id AND r.kind='util') useful
                   FROM v12_social_posts p JOIN users u ON u.id=p.author_id
                   LEFT JOIN stores s ON s.id=p.store_id LEFT JOIN products pr ON pr.id=p.product_id
                   WHERE p.status='visible' AND (p.expires_at IS NULL OR p.expires_at>?)
                   ORDER BY p.created_at DESC LIMIT 350''',(now(),))
            records=[r for r in rows if (not kind or r['kind']==kind) and (store_id is None or r['store_id']==store_id) and can_see(db,r,user['id'])][:limit]
            for r in records:
                own=one(db,'SELECT kind FROM v12_social_reactions WHERE post_id=? AND user_id=?',(r['id'],user['id']))
                r['my_reaction']=own['kind'] if own else None
            return {'items':records}

    @app.post('/api/v12/social')
    def new_social(d:SocialCreate,user=Depends(auth)):
        if d.kind=='oferta' and d.price_cents is None:raise HTTPException(400,'Si publicas un precio, indica el importe observado.')
        with connect() as db:
            if d.store_id and not one(db,'SELECT id FROM stores WHERE id=?',(d.store_id,)):raise HTTPException(400,'Establecimiento desconocido')
            if d.product_id and not one(db,'SELECT id FROM products WHERE id=?',(d.product_id,)):raise HTTPException(400,'Producto desconocido')
            recent=one(db,'SELECT COUNT(*) n FROM v12_social_posts WHERE author_id=? AND created_at>?',(user['id'],(dt.now(timezone.utc)-timedelta(minutes=15)).isoformat(timespec='seconds')))
            if recent['n']>=8:raise HTTPException(429,'Has publicado muchos mensajes. Vuelve a intentarlo más tarde.')
            ttl=timedelta(hours=12) if d.kind in ('oferta','repuesto','agotado') else timedelta(days=90)
            c=db.execute('''INSERT INTO v12_social_posts(author_id,kind,store_id,product_id,visibility,title,body,price_cents,observed_at,created_at,expires_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(user['id'],d.kind,d.store_id,d.product_id,d.visibility,d.title.strip(),d.body.strip(),d.price_cents,now(),now(),(dt.now(timezone.utc)+ttl).isoformat(timespec='seconds')))
        return {'id':c.lastrowid,'status':'usuario_no_verificado','expires_in_hours':round(ttl.total_seconds()/3600)}

    @app.get('/api/v12/social/{post_id}/comments')
    def comments(post_id:int,user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT * FROM v12_social_posts WHERE id=? AND status=?',(post_id,'visible'))
            if not p or not can_see(db,p,user['id']):raise HTTPException(404,'Publicación no disponible')
            return {'items':many(db,'SELECT c.id,c.body,c.created_at,u.display_name author_name FROM v12_social_comments c JOIN users u ON c.author_id=u.id WHERE c.post_id=? ORDER BY c.id DESC LIMIT 80',(post_id,))}

    @app.post('/api/v12/social/{post_id}/comments')
    def add_comment(post_id:int,d:Comment,user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT * FROM v12_social_posts WHERE id=? AND status=?',(post_id,'visible'))
            if not p or not can_see(db,p,user['id']):raise HTTPException(404,'Publicación no disponible')
            n=one(db,'SELECT COUNT(*) n FROM v12_social_comments WHERE author_id=? AND created_at>?',(user['id'],(dt.now(timezone.utc)-timedelta(minutes=15)).isoformat(timespec='seconds')))
            if n['n']>=20:raise HTTPException(429,'Demasiados comentarios en poco tiempo')
            c=db.execute('INSERT INTO v12_social_comments(post_id,author_id,body,created_at) VALUES(?,?,?,?)',(post_id,user['id'],d.body.strip(),now()))
            return {'id':c.lastrowid}

    @app.post('/api/v12/social/{post_id}/react')
    def react(post_id:int,d:React,user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT * FROM v12_social_posts WHERE id=? AND status=?',(post_id,'visible'))
            if not p or not can_see(db,p,user['id']):raise HTTPException(404,'Publicación no disponible')
            if d.kind=='none':db.execute('DELETE FROM v12_social_reactions WHERE post_id=? AND user_id=?',(post_id,user['id']))
            else:db.execute('INSERT INTO v12_social_reactions(post_id,user_id,kind) VALUES(?,?,?) ON CONFLICT(post_id,user_id) DO UPDATE SET kind=excluded.kind',(post_id,user['id'],d.kind))
            return {'ok':True,'reaction':None if d.kind=='none' else d.kind}

    @app.post('/api/v12/social/{post_id}/flag')
    def social_flag(post_id:int,d:Flag,user=Depends(auth)):
        with connect() as db:
            p=one(db,'SELECT * FROM v12_social_posts WHERE id=?',(post_id,))
            if not p:raise HTTPException(404,'Publicación no encontrada')
            if p['author_id']==user['id']:raise HTTPException(400,'No puedes denunciar tu propia publicación')
            if not can_see(db,p,user['id']):raise HTTPException(404,'Publicación no disponible')
            db.execute('INSERT OR IGNORE INTO v12_social_flags(post_id,user_id,reason) VALUES(?,?,?)',(post_id,user['id'],d.reason))
            count=one(db,'SELECT COUNT(*) n FROM v12_social_flags WHERE post_id=?',(post_id,))['n']
            if count>=3:db.execute('UPDATE v12_social_posts SET status=? WHERE id=?',('under_review',post_id))
            return {'ok':True,'status':'under_review' if count>=3 else 'flagged'}

    def offers_visible(db,uid):
        rows=many(db,'''SELECT o.*,u.display_name author_name,s.name store_name
                    FROM v12_neighbor_offers o JOIN users u ON u.id=o.creator_id
                    LEFT JOIN stores s ON s.id=o.store_id WHERE o.until_at>? AND o.status IN ('open','accepted')
                    ORDER BY o.created_at DESC LIMIT 120''',(now(),))
        return [r for r in rows if r['creator_id']==uid or friend(db,r['creator_id'],uid)]

    @app.get('/api/v12/neighbor/offers')
    def neighbor_list(user=Depends(auth)):
        with connect() as db:return {'items':offers_visible(db,user['id'])}

    @app.post('/api/v12/neighbor/offers')
    def neighbor_create(d:NeighborOffer,user=Depends(auth)):
        with connect() as db:
            if d.store_id and not one(db,'SELECT id FROM stores WHERE id=?',(d.store_id,)):raise HTTPException(400,'Tienda desconocida')
            c=db.execute('INSERT INTO v12_neighbor_offers(creator_id,store_id,note,area_label,until_at,created_at) VALUES(?,?,?,?,?,?)',
                    (user['id'],d.store_id,d.note.strip(),d.area_label.strip(),(dt.now(timezone.utc)+timedelta(minutes=d.minutes_available)).isoformat(timespec='seconds'),now()))
            return {'id':c.lastrowid,'visibility':'friends_only','status':'open','notice':'Coordinación entre amistades, no servicio comercial ni venta de alimentos. No compartir domicilios.'}

    @app.post('/api/v12/neighbor/offers/{offer_id}/action')
    def neighbor_action(offer_id:int,d:NeighborAccept,user=Depends(auth)):
        with connect() as db:
            o=one(db,'SELECT * FROM v12_neighbor_offers WHERE id=?',(offer_id,))
            if not o or (o['creator_id']!=user['id'] and not friend(db,o['creator_id'],user['id'])):raise HTTPException(404,'Oferta no disponible')
            if d.action=='accept':
                if o['creator_id']==user['id']:raise HTTPException(400,'No puedes aceptar tu propio ofrecimiento')
                if o['status']!='open' or o['until_at']<now():raise HTTPException(409,'Este ofrecimiento ya no está libre')
                result=db.execute('UPDATE v12_neighbor_offers SET status=?,accepted_by=? WHERE id=? AND status=?',('accepted',user['id'],offer_id,'open'))
                if result.rowcount!=1:raise HTTPException(409,'Otro contacto ya aceptó esta ayuda')
            elif d.action=='cancel':
                if o['creator_id']!=user['id']:raise HTTPException(403,'Solo quien publica puede cancelar')
                db.execute('UPDATE v12_neighbor_offers SET status=? WHERE id=?',('cancelled',offer_id))
            elif d.action=='complete':
                if o['creator_id']!=user['id'] and o['accepted_by']!=user['id']:raise HTTPException(403,'No autorizado')
                if o['status']!='accepted':raise HTTPException(409,'Debe haberse aceptado antes')
                db.execute('UPDATE v12_neighbor_offers SET status=? WHERE id=?',('done',offer_id))
            return {'ok':True,'status':'accepted' if d.action=='accept' else ('cancelled' if d.action=='cancel' else 'done')}

    @app.get('/api/v12/observed-prices/nearby')
    def local_price_observations(lat:float=Query(40.4168,ge=-90,le=90),
              lon:float=Query(-3.7038,ge=-180,le=180),
              radius_km:float=Query(5,ge=.2,le=20),
              max_age_days:int=Query(7,ge=1,le=30),
              limit:int=Query(80,ge=1,le=200)):
        # Crowdsourced user observations, NOT official offers or verified current stock.
        center_madrid(lat,lon)
        cutoff=(dt.now(timezone.utc)-timedelta(days=max_age_days)).isoformat(timespec='seconds')
        with connect() as db:
            stores=list_nearby(db,lat,lon,radius_km,'','',500)
            if not stores:return {'items':[],'source':'aportaciones usuarios','verified_by_retailer':False,'freshness_days':max_age_days}
            selected={x['id']:x for x in stores}
            ids=','.join('?'*len(selected))
            rows=many(db,f'''SELECT po.id,po.product_id,po.store_id,po.amount_cents,po.source_type,
                     po.observed_at,p.name product_name,s.name store_name,s.chain
                     FROM price_observations po JOIN products p ON p.id=po.product_id
                     JOIN stores s ON s.id=po.store_id
                     WHERE po.store_id IN ({ids}) AND po.observed_at>=?
                     ORDER BY po.observed_at DESC,po.id DESC LIMIT 600''',(*selected,cutoff))
        first=set();result=[]
        for r in rows:
            key=(r['product_id'],r['store_id'])
            if key in first:continue
            first.add(key);r['distance_km']=selected[r['store_id']]['distance_km']
            r['verified_by_retailer']=False
            result.append(r)
            if len(result)>=limit:break
        return {'items':result,'source':'Observaciones declaradas por usuarios, no verificadas por el establecimiento',
                'verified_by_retailer':False,'freshness_days':max_age_days,
                'notice':'Sin observaciones no puede inferirse ausencia de descuentos. Los precios pueden haber cambiado.'}

    @app.get('/api/v12/sources')
    def data_sources():
        return {'stores':'OpenStreetMap / ODbL, importados con permiso y fecha de fuente; registros manuales no verificados',
                'products':'Muestra oficial web por cadena, no surtido físico; Open Food Facts ODbL solo bajo sus condiciones',
                'prices':'Observaciones comunitarias u Open Prices ODbL; no garantía de actualidad, no hay stock ni API oficial de cadenas',
                'real_time':False,'commercial_stock_integration':False}
