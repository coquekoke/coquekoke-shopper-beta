import pytest
from datetime import datetime,timedelta,timezone
from .conftest import create_basket

def test_auth_session_and_self_details(env):
    c,login=env
    assert c.get('/').status_code==200
    assert c.get('/api/bootstrap').status_code==401
    assert c.post('/api/auth/login',json={'username':'maria_demo','password':'wrong'}).status_code==401
    h=login(); j=c.get('/api/bootstrap',headers=h).json()
    assert j['me']['username']=='maria_demo'
    assert 'salt' not in str(j) and 'passhash' not in str(j)
    assert j['baskets'][0]['kind']=='actual'
    assert c.post('/api/auth/logout',headers=h).status_code==200
    assert c.get('/api/me',headers=h).status_code==401

def test_register_creates_private_actual_basket(env):
    c,login=env
    r=c.post('/api/auth/register',json={'username':'mia_12','display_name':'Mía de prueba','password':'ClaveDificil12345!'})
    assert r.status_code==200
    h={'Authorization':'Bearer '+r.json()['token']}
    j=c.get('/api/bootstrap',headers=h).json()
    assert len(j['baskets'])==1 and j['baskets'][0]['kind']=='actual'
    assert j['pantry']==[] and j['places']==[]
    assert c.post('/api/auth/register',json={'username':'mia_12','display_name':'Otra','password':'ClaveDificil12345!'}).status_code==409
    assert c.post('/api/auth/register',json={'username':'X','display_name':'Pepe','password':'1234567890123'}).status_code==422

def test_shared_basket_permissions_and_single_use_invite(env):
    c,login=env
    a=login();b=login('lucas_demo')
    bid=create_basket(c,a)
    assert c.get(f'/api/baskets/{bid}',headers=b).status_code==403
    assert c.put(f'/api/baskets/{bid}/items/1',json={'quantity':2},headers=a).status_code==200
    r=c.post(f'/api/baskets/{bid}/invite',json={'role':'reader'},headers=a); assert r.status_code==200
    code=r.json()['code']
    assert c.post('/api/invitations/redeem',json={'code':code},headers=a).status_code==400
    assert c.post('/api/invitations/redeem',json={'code':code},headers=b).status_code==200
    assert c.post('/api/invitations/redeem',json={'code':code},headers=b).status_code==404
    assert c.get(f'/api/baskets/{bid}',headers=b).status_code==200
    assert c.put(f'/api/baskets/{bid}/items/1',json={'quantity':3},headers=b).status_code==403
    assert c.post(f'/api/baskets/{bid}/invite',json={'role':'editor'},headers=b).status_code==403
    code2=c.post(f'/api/baskets/{bid}/invite',json={'role':'editor'},headers=a).json()['code']
    assert c.post('/api/invitations/redeem',json={'code':code2},headers=b).status_code==200
    assert c.put(f'/api/baskets/{bid}/items/1',json={'quantity':4},headers=b).status_code==200
    assert c.get(f'/api/baskets/{bid}',headers=a).json()['items'][0]['quantity']==4

def test_friend_invite_and_privacy(env):
    c,login=env;a=login();b=login('lucas_demo')
    code=c.post('/api/friends/invite',headers=a).json()['code']
    assert c.post('/api/invitations/redeem',json={'code':code},headers=b).status_code==200
    friends=c.get('/api/bootstrap',headers=a).json()['friends']
    assert len(friends)==1 and friends[0]['username']=='lucas_demo'
    assert 'friend_code' not in str(friends)
    assert len(c.get('/api/bootstrap',headers=b).json()['friends'])==1

def test_places_and_store_network_isolated(env):
    c,login=env;a=login();b=login('lucas_demo')
    r=c.post('/api/places',json={'name':'Casa prueba','address':'Dirección ficticia'},headers=a);pid=r.json()['id']
    assert c.post(f'/api/places/{pid}/stores',json={'store_id':1},headers=b).status_code==403
    assert c.post(f'/api/places/{pid}/stores',json={'store_id':1},headers=a).status_code==200
    assert any(n['place_id']==pid for n in c.get('/api/bootstrap',headers=a).json()['network'])
    assert c.get('/api/bootstrap',headers=b).json()['network']==[]
    assert c.post('/api/places',json={'name':'Otra','lat':39.1},headers=a).status_code==400
    r=c.post('/api/stores',json={'name':'Tienda aportada','chain':'Local','address':'Calle inventada 1, Ciudad','municipality':'Ciudad'},headers=a)
    assert r.json()['note'].startswith('Aportación')
    assert any(s['name']=='Tienda aportada' and s['source_type']=='aporte_manual_no_verificado' for s in c.get('/api/bootstrap',headers=b).json()['stores'])

def test_pantry_isolation_close_and_duplicate_warning_source(env):
    c,login=env;a=login();b=login('lucas_demo')
    r=c.post('/api/pantry',json={'product_id':1,'quantity':2,'unit':'ud','expires_on':'2026-11-28'},headers=a)
    assert r.status_code==200;pid=r.json()['id']
    assert c.patch(f'/api/pantry/{pid}',json={'state':'used'},headers=b).status_code==404
    assert c.patch(f'/api/pantry/{pid}',json={'state':'used'},headers=a).status_code==200
    assert c.patch(f'/api/pantry/{pid}',json={'state':'discarded'},headers=a).status_code==409
    assert c.get('/api/bootstrap',headers=b).json()['pantry']==[]
    assert c.post('/api/pantry',json={'quantity':1,'unit':'kg'},headers=a).status_code==400

def test_price_comparison_requires_full_coverage_and_can_split(env):
    c,login=env;h=login();b=create_basket(c,h)
    assert c.put(f'/api/baskets/{b}/items/1',json={'quantity':2},headers=h).status_code==200
    assert c.put(f'/api/baskets/{b}/items/2',json={'quantity':1},headers=h).status_code==200
    initial=c.get(f'/api/baskets/{b}/compare',headers=h).json()
    assert initial['best'] is None and initial['coverage']==0
    for pid,sid,price in [(1,1,300),(1,2,250),(2,1,600),(2,2,1000)]:
        assert c.post('/api/prices',json={'product_id':pid,'store_id':sid,'amount_cents':price,'source_type':'etiqueta'},headers=h).status_code==200
    comp=c.get(f'/api/baskets/{b}/compare?extra_stop_cents=0',headers=h).json()
    assert comp['coverage']==2
    assert comp['best']['items_total_cents']==1100 # 2*250 at store 2 + 600 at store 1
    assert comp['best']['stops']==2
    assert comp['single_store_reference_cents']==1200
    expensive=c.get(f'/api/baskets/{b}/compare?extra_stop_cents=800',headers=h).json()
    assert expensive['best']['stops']==1 and expensive['best']['items_total_cents']==1200
    # Restrict to one place/store: combinations only use the selected network
    pid=c.post('/api/places',json={'name':'Oficina'},headers=h).json()['id']
    c.post(f'/api/places/{pid}/stores',json={'store_id':2},headers=h)
    c.patch(f'/api/baskets/{b}',json={'place_id':pid},headers=h)
    only=c.get(f'/api/baskets/{b}/compare',headers=h).json()
    assert len(only['by_store'])==1 and only['by_store'][0]['store_id']==2

def test_price_validity_and_product_barcode(env):
    c,login=env;h=login()
    assert c.get('/api/barcodes/3017620422003',headers=h).json()['found']
    assert c.get('/api/barcodes/12345',headers=h).status_code==400
    assert c.get('/api/barcodes/4006381333931',headers=h).json()['found'] is False
    assert c.post('/api/products',json={'name':'Malo','category':'Otro','gtin':'1234567890123'},headers=h).status_code==400
    p=c.post('/api/products',json={'name':'Yogur marca X','category':'Lácteos'},headers=h)
    assert p.status_code==200
    assert c.post('/api/prices',json={'product_id':p.json()['id'],'store_id':999,'amount_cents':140,'source_type':'etiqueta'},headers=h).status_code==404

def test_live_feed_verification_spam_and_flags(env):
    c,login=env;a=login();b=login('lucas_demo')
    r=c.post('/api/live',json={'store_id':1,'product_id':1,'kind':'agotado','note':'No lo vi en el pasillo'},headers=a)
    assert r.status_code==200;rid=r.json()['id']
    assert c.post('/api/live',json={'store_id':1,'product_id':1,'kind':'agotado'},headers=a).status_code==429
    assert c.post(f'/api/live/{rid}/confirm',headers=a).status_code==400
    assert c.post(f'/api/live/{rid}/confirm',headers=b).status_code==200
    assert c.get('/api/bootstrap',headers=b).json()['reports'][0]['confirmations']==1
    assert c.post(f'/api/live/{rid}/flag',json={'reason':'información inexacta'},headers=b).status_code==200
    assert c.post('/api/live',json={'store_id':1,'product_id':1,'kind':'descuento','price_cents':200},headers=b).status_code==200

def test_orders_never_send_to_non_connected_stores(env):
    c,login=env;h=login();b=create_basket(c,h)
    c.put(f'/api/baskets/{b}/items/1',json={'quantity':1},headers=h)
    start=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(timespec='minutes')
    payload={'basket_id':b,'store_id':1,'mode':'pickup_store','window_start':start,'window_mins':15,'notice_hours':24}
    assert c.post('/api/order-drafts',json=payload,headers=h).status_code==409
    payload['mode']='pickup_shopper';r=c.post('/api/order-drafts',json=payload,headers=h)
    assert r.status_code==200 and r.json()['status']=='DRAFT_NOT_SENT'
    assert c.delete(f'/api/baskets/{b}',headers=h).status_code==409
    payload['notice_hours']=168
    assert c.post('/api/order-drafts',json=payload,headers=h).status_code==400
    payload['mode']='delivery_shopper';payload['notice_hours']=6
    assert c.post('/api/order-drafts',json=payload,headers=h).status_code==400

def test_professional_application_never_activates_jobs(env):
    c,login=env;h=login()
    r=c.post('/api/shopper/profile',json={'travel_mode':'bike','min_notice_hours':1,'min_window_mins':120,'max_distance_km':8},headers=h)
    assert r.status_code==200 and r.json()['status']=='draft'
    assert c.post('/api/shopper/apply',headers=h).json()['status']=='pending_mock_review'
    assert c.post('/api/shopper/apply',headers=h).status_code==409
    assert c.get('/api/bootstrap',headers=h).json()['shopper']['status']=='pending_mock_review'

def test_economics_and_account_export(env):
    c,login=env;h=login()
    e=c.post('/api/economics',json={'customer_fee_eur':16,'worker_eur':10,'transport_eur':1.4,'payment_eur':.6,'support_eur':.4,'reserve_eur':.8,'monthly_fixed_eur':1500},headers=h).json()
    assert e['contribution_per_order_eur']==2.8 and e['orders_to_cover_fixed']==536
    exp=c.get('/api/account/export',headers=h)
    assert exp.status_code==200 and 'password' not in exp.text and 'token_digest' not in exp.text

def test_web_static_security_headers(env):
    c,login=env
    r=c.get('/')
    assert r.status_code==200 and 'SHOPPER 9.0' in r.text
    assert 'nosniff' in r.headers['x-content-type-options']
    assert c.get('/static/app.js').status_code==200
    assert c.get('/static/style.css').status_code==200

def test_quick_private_list_and_checkout_progress(env):
    c,login=env;a=login();b=login('lucas_demo');bid=create_basket(c,a)
    r=c.post(f'/api/baskets/{bid}/free-items',json={'title':'Servilletas para fiesta','quantity':4},headers=a)
    assert r.status_code==200;fid=r.json()['id']
    assert c.get(f'/api/baskets/{bid}',headers=b).status_code==403
    assert c.patch(f'/api/baskets/{bid}/free-items/{fid}',json={'checked':True},headers=b).status_code==403
    assert c.patch(f'/api/baskets/{bid}/free-items/{fid}',json={'checked':True},headers=a).status_code==200
    out=c.get(f'/api/baskets/{bid}',headers=a).json()
    assert out['checked_count']==1 and out['items'][0]['name']=='Servilletas para fiesta'
    compare=c.get(f'/api/baskets/{bid}/compare',headers=a).json()
    assert compare['best'] is None and 'Servilletas para fiesta' in compare['unpriced']
    assert c.post(f'/api/baskets/{bid}/reset-checks',headers=a).status_code==200
    assert c.get(f'/api/baskets/{bid}',headers=a).json()['checked_count']==0
    assert c.patch(f'/api/baskets/{bid}/free-items/{fid}',json={'quantity':0},headers=a).status_code==200
    assert c.get(f'/api/baskets/{bid}',headers=a).json()['items']==[]

def test_shared_shopping_progress_and_member_revocation(env):
    c,login=env;a=login();b=login('lucas_demo');bid=create_basket(c,a)
    c.put(f'/api/baskets/{bid}/items/1',json={'quantity':1},headers=a)
    code=c.post(f'/api/baskets/{bid}/invite',json={'role':'editor'},headers=a).json()['code']
    c.post('/api/invitations/redeem',json={'code':code},headers=b)
    assert c.patch(f'/api/baskets/{bid}/items/1/check',json={'checked':True},headers=b).status_code==200
    assert c.get(f'/api/baskets/{bid}',headers=a).json()['checked_count']==1
    assert c.delete(f'/api/baskets/{bid}/members/2',headers=a).status_code==200
    assert c.get(f'/api/baskets/{bid}',headers=b).status_code==403
