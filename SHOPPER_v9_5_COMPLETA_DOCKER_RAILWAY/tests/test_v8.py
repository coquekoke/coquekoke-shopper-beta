"""Incremental V8 test suite. Always uses an isolated per-test SQLite database."""
from .conftest import env,create_basket


def test_shelf_observations_price_and_store_isolation(env):
    client,login=env
    a,b=login(),login('lucas_demo')
    s=client.get('/api/stores/1/shelf',headers=a)
    assert s.status_code==200 and s.json()['items']==[]
    assert s.json()['status']=='carta_comunitaria_parcial'
    assert client.post('/api/store-sightings',json={'store_id':1,'product_id':1,'kind':'seen','note':'En la zona de desayunos'},headers=a).status_code==200
    assert client.post('/api/store-sightings',json={'store_id':1,'product_id':1,'kind':'seen'},headers=a).status_code==429
    assert client.post('/api/store-sightings',json={'store_id':2,'product_id':1,'kind':'not_found'},headers=b).status_code==200
    assert client.post('/api/store-sightings',json={'store_id':999,'product_id':1,'kind':'seen'},headers=b).status_code==404
    assert client.post('/api/prices',json={'product_id':1,'store_id':1,'amount_cents':360},headers=b).status_code==200
    shelf1=client.get('/api/stores/1/shelf',headers=b).json()['items']
    assert len(shelf1)==1 and shelf1[0]['last_seen_kind']=='seen' and shelf1[0]['price_cents']==360
    shelf2=client.get('/api/stores/2/shelf',headers=a).json()['items']
    assert len(shelf2)==1 and shelf2[0]['last_seen_kind']=='not_found' and shelf2[0]['price_cents'] is None
    assert client.get('/api/stores/1/shelf').status_code==401


def test_watches_are_private_and_only_notify_on_new_activity(env):
    client,login=env
    a,b=login(),login('lucas_demo')
    assert client.post('/api/prices',json={'product_id':1,'store_id':1,'amount_cents':150},headers=a).status_code==200
    w=client.post('/api/watches',json={'product_id':1,'store_id':1,'threshold_cents':200},headers=a)
    assert w.status_code==200
    wid=w.json()['id']
    assert client.get('/api/bootstrap',headers=a).json()['watch_alerts']==[]  # old observation
    assert client.post('/api/prices',json={'product_id':1,'store_id':2,'amount_cents':100},headers=b).status_code==200
    assert client.get('/api/bootstrap',headers=a).json()['watch_alerts']==[]  # other shop
    assert client.post('/api/prices',json={'product_id':1,'store_id':1,'amount_cents':175},headers=b).status_code==200
    alerts=client.get('/api/bootstrap',headers=a).json()['watch_alerts']
    assert len(alerts)==1 and alerts[0]['amount_cents']==175 and alerts[0]['kind']=='price'
    assert client.get('/api/bootstrap',headers=b).json()['watches']==[]
    assert client.delete(f'/api/watches/{wid}',headers=b).status_code==404
    assert client.post('/api/watches',json={'product_id':1,'store_id':1,'threshold_cents':125},headers=a).json()['updated'] is True
    assert client.get('/api/bootstrap',headers=a).json()['watch_alerts']==[]
    assert client.post('/api/live',json={'store_id':1,'product_id':1,'kind':'repuesto'},headers=b).status_code==200
    alerts=client.get('/api/bootstrap',headers=a).json()['watch_alerts']
    assert len(alerts)==1 and alerts[0]['kind']=='restocked'
    assert client.delete(f'/api/watches/{wid}',headers=a).status_code==200


def test_basket_copy_to_actual_owner_and_shared_reader(env):
    client,login=env
    a,b=login(),login('lucas_demo')
    source=create_basket(client,a,title='Mensual')
    client.put(f'/api/baskets/{source}/items/1',json={'quantity':2},headers=a)
    client.post(f'/api/baskets/{source}/free-items',json={'title':'Leche sin lactosa','quantity':3},headers=a)
    assert client.post(f'/api/baskets/{source}/copy-to-actual',headers=b).status_code==403
    code=client.post(f'/api/baskets/{source}/invite',json={'role':'reader'},headers=a).json()['code']
    assert client.post('/api/invitations/redeem',json={'code':code},headers=b).status_code==200
    r=client.post(f'/api/baskets/{source}/copy-to-actual',headers=b)
    assert r.status_code==200 and r.json()['copied_lines']==2
    actual=r.json()['target_id'];lines=client.get(f'/api/baskets/{actual}',headers=b).json()['items']
    assert len(lines)==2
    assert any(i['product_id']==1 and i['quantity']==2 for i in lines)
    assert any(i['name']=='Leche sin lactosa' for i in lines)
    assert client.post(f'/api/baskets/{actual}/copy-to-actual',headers=b).status_code==400
    assert client.get(f'/api/baskets/{actual}',headers=a).status_code==403


def test_partial_pantry_consumption_discard_and_owner_permissions(env):
    client,login=env
    a,b=login(),login('lucas_demo')
    pid=client.post('/api/pantry',json={'product_id':1,'quantity':2,'unit':'kg'},headers=a).json()['id']
    assert client.post(f'/api/pantry/{pid}/portion',json={'quantity':0.5,'kind':'used'},headers=b).status_code==404
    assert client.post(f'/api/pantry/{pid}/portion',json={'quantity':3,'kind':'used'},headers=a).status_code==400
    r=client.post(f'/api/pantry/{pid}/portion',json={'quantity':1.25,'kind':'used'},headers=a)
    assert r.status_code==200 and r.json()['remaining']==0.75
    r=client.post(f'/api/pantry/{pid}/portion',json={'quantity':0.75,'kind':'discarded'},headers=a)
    assert r.status_code==200 and r.json()['state']=='discarded'
    assert client.post(f'/api/pantry/{pid}/portion',json={'quantity':0.1,'kind':'used'},headers=a).status_code==409
    boot=client.get('/api/bootstrap',headers=a).json()
    assert len(boot['recent_movements'])==2
    assert boot['pantry'][0]['state']=='discarded'
    assert client.get('/api/bootstrap',headers=b).json()['recent_movements']==[]


def test_purchase_history_snapshot_private_and_zero_is_valid(env):
    client,login=env
    a,b=login(),login('lucas_demo')
    bid=create_basket(client,a)
    assert client.post('/api/shopping-runs',json={'basket_id':bid,'paid_cents':800},headers=a).status_code==400
    client.post(f'/api/baskets/{bid}/free-items',json={'title':'Pan','quantity':2},headers=a)
    r=client.post('/api/shopping-runs',json={'basket_id':bid,'store_id':1,'paid_cents':0,'minutes_spent':0,'notes':'Prueba gratuita'},headers=a)
    assert r.status_code==200
    assert client.post('/api/shopping-runs',json={'basket_id':bid,'paid_cents':-1},headers=a).status_code==422
    assert client.post('/api/shopping-runs',json={'basket_id':bid,'paid_cents':500},headers=b).status_code==403
    client.post(f'/api/baskets/{bid}/free-items',json={'title':'Plátanos','quantity':1},headers=a)
    own=client.get('/api/bootstrap',headers=a).json()['shopping_runs']
    assert len(own)==1 and own[0]['paid_cents']==0
    import json
    items=json.loads(own[0]['item_snapshot'])
    assert len(items)==1 and items[0]['name']=='Pan'  # immutable at time recorded
    assert client.get('/api/bootstrap',headers=b).json()['shopping_runs']==[]

def test_openfoodfacts_optional_api_gate_and_safe_mapping(env,monkeypatch):
    client,login=env;h=login()
    assert client.get('/api/barcodes/123/external',headers=h).status_code==400
    monkeypatch.delenv('SHOPPER_OFF_USER_AGENT',raising=False)
    assert client.get('/api/barcodes/3017620422003/external',headers=h).status_code==503
    monkeypatch.setenv('SHOPPER_OFF_USER_AGENT','SHOPPER/8.0 (owner@example.org)')
    import main
    main._OFF_CALLS.clear()
    import urllib.request,io,json
    class MockResponse:
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self,n):return json.dumps({'product':{'product_name_es':'Crema avellanas prueba','brands':'Marca demo','ingredients_text_es':'Ejemplo de ingrediente','nutriscore_grade':'e'}}).encode()
    monkeypatch.setattr(urllib.request,'urlopen',lambda req,timeout:MockResponse())
    result=client.get('/api/barcodes/3017620422003/external',headers=h)
    assert result.status_code==200 and result.json()['name']=='Crema avellanas prueba'
    assert 'stock' in result.json()['note'] and result.json()['source']=='Open Food Facts'
    assert client.get('/api/barcodes/3017620422003/external').status_code==401

def test_account_export_includes_manual_items_and_only_own_contributions(env):
    client,login=env;a=login();b=login('lucas_demo')
    bid=create_basket(client,a)
    client.post(f'/api/baskets/{bid}/free-items',json={'title':'Texto en lista','quantity':2},headers=a)
    client.post('/api/prices',json={'store_id':1,'product_id':1,'amount_cents':450},headers=b)
    client.post('/api/prices',json={'store_id':1,'product_id':1,'amount_cents':420},headers=a)
    client.post('/api/store-sightings',json={'store_id':1,'product_id':1,'kind':'seen'},headers=a)
    export=client.get('/api/account/export',headers=a)
    assert export.status_code==200
    data=export.json()
    assert any(any(i['title']=='Texto en lista' for i in k['manual_items']) for k in data['basket_details'])
    assert len(data['my_price_observations'])==1
    assert len(data['my_store_sightings'])==1
    assert 'passhash' not in export.text and 'token_digest' not in export.text


def test_shopping_run_remains_after_delete_of_original_basket(env):
    client,login=env;a=login()
    bid=create_basket(client,a)
    client.post(f'/api/baskets/{bid}/free-items',json={'title':'Tomates','quantity':2},headers=a)
    assert client.post('/api/shopping-runs',json={'basket_id':bid,'paid_cents':312},headers=a).status_code==200
    assert client.delete(f'/api/baskets/{bid}',headers=a).status_code==200
    h=client.get('/api/bootstrap',headers=a).json()['shopping_runs']
    assert len(h)==1 and h[0]['basket_id'] is None and h[0]['basket_name']=='Cesta evento'
