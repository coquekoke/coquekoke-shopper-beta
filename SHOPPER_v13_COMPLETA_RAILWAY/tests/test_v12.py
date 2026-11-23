"""V12: source-aware geo, received-only pantry, socially-safe collaboration."""
from datetime import datetime,timezone,timedelta
from db import connect, one

def test_v12_frontend_and_public_sources(env):
    c,login=env
    assert c.get('/health').json()['version']=='13.0'
    assert 'SHOPPER 13 · Tus recetas y tarjetas' in c.get('/').text
    assert c.get('/v11').status_code==200
    assert c.get('/v10').status_code==200
    assert c.get('/previous').status_code==200
    assert c.get('/static/v12.js').status_code==200
    assert c.get('/static/v12.css').status_code==200
    assert c.get('/api/v12/sources').json()['real_time'] is False
    assert c.get('/api/bootstrap').status_code==401
    assert c.get('/api/v12/social').status_code==401

def test_v12_osm_import_and_nearby_geolocation(env):
    c,login=env
    from v12api import import_overpass
    rows=[{'type':'node','id':123,'lat':40.4241,'lon':-3.698,'tags':{'shop':'supermarket','name':'Supermercado Example OSM','brand':'DIA','addr:street':'Calle Ejemplo','addr:housenumber':'12','addr:city':'Madrid'}},
          {'type':'way','id':456,'center':{'lat':40.4521,'lon':-3.702},'tags':{'shop':'supermarket','name':'Mercado de ejemplo','brand':'Lidl','addr:street':'Calle Norte','addr:housenumber':'8'}}]
    with connect() as db:
        assert import_overpass(db,rows)['added']==2
    with connect() as db:
        assert import_overpass(db,rows)['added']==0
    a=c.get('/api/v12/stores/nearby?lat=40.4241&lon=-3.698&radius_km=1').json()
    assert len(a['items'])==1 and a['items'][0]['distance_km']==0
    assert a['items'][0]['source_type']=='openstreetmap'
    assert c.get('/api/v12/stores/nearby?lat=34&lon=2').status_code==400
    assert c.get('/api/v12/stores/nearby?lat=40.4&lon=-3.7&radius_km=31').status_code==422
    h=login();p=c.post('/api/places',json={'name':'Casa','lat':40.4,'lon':-3.7},headers=h)
    assert p.status_code==200
    assert c.patch(f'/api/v12/places/{p.json()["id"]}/coordinates',json={'lat':40.4241,'lon':-3.698},headers=h).status_code==200
    other=login('lucas_demo')
    assert c.patch(f'/api/v12/places/{p.json()["id"]}/coordinates',json={'lat':40.41,'lon':-3.6},headers=other).status_code==403

def test_purchase_cannot_touch_pantry_before_receipt_and_no_duplicate(env):
    c,login=env;h=login()
    b=c.post('/api/baskets',json={'kind':'ocasional','title':'Compra real'},headers=h).json()['id']
    c.post(f'/api/baskets/{b}/free-items',json={'title':'Tomates','quantity':2},headers=h)
    purchase=c.post('/api/v12/purchases',headers=h,json={'basket_id':b,'paid_cents':1320,
        'received':False,'pantry_mode':'add','extras':[{'name':'Pan','quantity':1,'unit':'ud'}]})
    assert purchase.status_code==200,purchase.text
    pid=purchase.json()['id']
    assert not any(x['custom_name']=='Tomates' for x in c.get('/api/bootstrap',headers=h).json()['pantry'])
    h2=login('lucas_demo')
    assert c.post(f'/api/v12/purchases/{pid}/receive',headers=h2,json={'pantry_mode':'add'}).status_code==404
    r=c.post(f'/api/v12/purchases/{pid}/receive',headers=h,json={'pantry_mode':'add'})
    assert r.json()['pantry_added']==2
    again=c.post(f'/api/v12/purchases/{pid}/receive',headers=h,json={'pantry_mode':'add'})
    assert again.json()['pantry_added']==0
    pantry=c.get('/api/bootstrap',headers=h).json()['pantry']
    assert sum(x['custom_name']=='Tomates' for x in pantry)==1
    assert sum(x['custom_name']=='Pan' for x in pantry)==1
    with connect() as db:
        assert one(db,'SELECT COUNT(*) n FROM v12_pantry_transfer WHERE purchase_id=?',(pid,))['n']==2

def test_purchase_autopantries_only_if_opted_in_and_received(env):
    c,login=env;h=login()
    assert c.get('/api/v12/pantry/settings',headers=h).json()['auto_pantry'] is False
    assert c.put('/api/v12/pantry/settings',json={'auto_pantry':True},headers=h).status_code==200
    r=c.post('/api/v12/purchases',headers=h,json={'paid_cents':480,'received':True,
         'extras':[{'name':'Arroz','quantity':1,'unit':'kg'}]})
    assert r.status_code==200 and r.json()['pantry_added']==1
    assert c.get('/api/v12/purchases',headers=h).json()['items'][0]['received_at'] is not None
    assert c.get('/api/v12/pantry/settings',headers=login('lucas_demo')).json()['auto_pantry'] is False
    bad=c.post('/api/v12/purchases',headers=h,json={'paid_cents':480,'received':True,'extras':[]})
    assert bad.status_code==400

def test_social_visibility_reactions_and_comments(env):
    c,login=env;h=login()
    post=c.post('/api/v12/social',headers=h,json={'kind':'nuevo','title':'Nuevo producto local','body':'Lo he visto hoy en tienda','visibility':'friends'})
    assert post.status_code==200,post.text
    pid=post.json()['id']
    hb=login('lucas_demo')
    assert not c.get('/api/v12/social',headers=hb).json()['items']
    assert c.post(f'/api/v12/social/{pid}/react',headers=hb,json={'kind':'util'}).status_code==404
    invite=c.post('/api/friends/invite',headers=h).json()['code']
    assert c.post('/api/invitations/redeem',headers=hb,json={'code':invite}).status_code==200
    assert len(c.get('/api/v12/social',headers=hb).json()['items'])==1
    assert c.post(f'/api/v12/social/{pid}/react',headers=hb,json={'kind':'util'}).status_code==200
    assert c.post(f'/api/v12/social/{pid}/comments',headers=hb,json={'body':'Lo buscaré'}).status_code==200
    assert c.get(f'/api/v12/social/{pid}/comments',headers=h).json()['items'][0]['body']=='Lo buscaré'
    assert c.get('/api/v12/social',headers=h).json()['items'][0]['useful']==1
    assert c.post('/api/v12/social',headers=h,json={'kind':'oferta','title':'Mega oferta','body':'Pollo rebajado','visibility':'community'}).status_code==400
    # Public posts visible to all signed-in users, not anonymous.
    assert c.get('/api/v12/social').status_code==401

def test_neighbor_offers_only_for_friends_and_no_auto_purchases(env):
    c,login=env;h=login()
    r=c.post('/api/v12/neighbor/offers',headers=h,json={'area_label':'Alcobendas norte','note':'Paso por la tienda, puedo traer dos cosas sencillas','minutes_available':60})
    assert r.status_code==200
    oid=r.json()['id']
    hb=login('lucas_demo')
    assert not c.get('/api/v12/neighbor/offers',headers=hb).json()['items']
    assert c.post(f'/api/v12/neighbor/offers/{oid}/action',headers=hb,json={'action':'accept'}).status_code==404
    code=c.post('/api/friends/invite',headers=h).json()['code']
    c.post('/api/invitations/redeem',headers=hb,json={'code':code})
    assert len(c.get('/api/v12/neighbor/offers',headers=hb).json()['items'])==1
    assert c.post(f'/api/v12/neighbor/offers/{oid}/action',headers=hb,json={'action':'accept'}).status_code==200
    assert c.post(f'/api/v12/neighbor/offers/{oid}/action',headers=hb,json={'action':'accept'}).status_code==409
    assert c.post(f'/api/v12/neighbor/offers/{oid}/action',headers=hb,json={'action':'complete'}).status_code==200

def test_v12_distinct_osm_shops_without_postal_addresses(env):
    c,login=env
    from v12api import import_overpass
    entries=[{'type':'node','id':780+i,'lat':40.413+i*.001,'lon':-3.71,
              'tags':{'shop':'supermarket','name':'Supermercado sin dirección'}} for i in range(3)]
    with connect() as db:
        first=import_overpass(db,entries)
        assert first['added']==3
        assert one(db,'SELECT COUNT(*) n FROM v12_store_osm')['n']==3
    stores=c.get('/api/v12/stores/nearby?lat=40.413&lon=-3.71&radius_km=1').json()['items']
    assert sum(s['name']=='Supermercado sin dirección' for s in stores)==3
    assert all('Dirección incompleta' in s['address'] for s in stores)

def test_v12_recent_local_user_price_observations(env):
    c,login=env;h=login()
    from v12api import import_overpass
    with connect() as db:
        import_overpass(db,[{'type':'node','id':880,'lat':40.408,'lon':-3.71,'tags':{
            'shop':'supermarket','name':'Tienda de observación'}}])
        st=one(db,'SELECT store_id FROM v12_store_osm WHERE osm_id=?',('node/880',))['store_id']
    assert c.post('/api/prices',json={'product_id':1,'store_id':st,'amount_cents':159,
                 'source_type':'etiqueta'},headers=h).status_code==200
    obs=c.get('/api/v12/observed-prices/nearby?lat=40.408&lon=-3.71&radius_km=1').json()
    assert obs['verified_by_retailer'] is False
    assert obs['items'][0]['amount_cents']==159
    assert obs['items'][0]['distance_km']==0
    assert len(c.get('/api/v12/observed-prices/nearby?lat=40.408&lon=-3.71&radius_km=1&max_age_days=1').json()['items'])==1

def test_v12_shared_basket_can_be_logged_by_invited_friend_only(env):
    c,login=env;owner=login()
    bid=c.post('/api/baskets',headers=owner,json={'title':'Cena compartida','kind':'evento'}).json()['id']
    c.post(f'/api/baskets/{bid}/free-items',headers=owner,json={'title':'Pasta', 'quantity':2})
    other=login('lucas_demo')
    assert c.post('/api/v12/purchases',headers=other,json={'basket_id':bid,'paid_cents':400}).status_code==403
    code=c.post(f'/api/baskets/{bid}/invite',headers=owner,json={'role':'reader'}).json()['code']
    assert c.post('/api/invitations/redeem',headers=other,json={'code':code}).status_code==200
    done=c.post('/api/v12/purchases',headers=other,json={'basket_id':bid,'paid_cents':400,'received':True,'pantry_mode':'skip'})
    assert done.status_code==200,done.text
    assert any(p['basket_title']=='Cena compartida' for p in c.get('/api/v12/purchases',headers=other).json()['items'])
    assert not any(p['basket_title']=='Cena compartida' for p in c.get('/api/v12/purchases',headers=owner).json()['items'])
