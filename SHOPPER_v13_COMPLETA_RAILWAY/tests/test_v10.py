import json
from urllib.parse import unquote
from fastapi.testclient import TestClient
from .conftest import create_basket

def test_retail_public_official_snapshot_and_branch_scope(env):
    c,login=env
    r=c.get('/api/retail/catalog')
    assert r.status_code==200
    data=r.json()
    assert len(data['items'])>=35
    assert 'NO inventario' in data['scope']
    assert all(x['source_url'].startswith('https://www.') and x['product_id'] for x in data['items'])
    assert all(x['observed_on']=='2026-11-23' for x in data['items'])
    dia=c.get('/api/retail/catalog?store_id=1').json()
    assert len(dia['items'])>10 and all(x['chain']=='DIA' for x in dia['items'])
    assert dia['store']['name'].startswith('DIA')
    # Sánchez Romero is a real pilot store, but has no verified chain-web list.
    other=c.get('/api/retail/catalog?store_id=2').json()
    assert other['items']==[] and 'NO inventario' in other['scope']

def test_catalog_items_can_be_added_to_families_but_do_not_become_local_stock(env):
    c,login=env
    h=login();bid=create_basket(c,h)
    item=c.get('/api/retail/catalog?chain=DIA&q=Arroz').json()['items'][0]
    pid=item['product_id']
    assert c.put(f'/api/baskets/{bid}/items/{pid}',json={'quantity':2},headers=h).status_code==200
    basket=c.get(f'/api/baskets/{bid}',headers=h).json()
    assert any(x['name']==item['name'] for x in basket['items'])
    summary=c.get(f'/api/retail/baskets/{bid}/summary?chain=DIA',headers=h).json()
    assert summary['complete'] and summary['estimated_total_cents']==2*item['price_cents']
    # No entry should have been manufactured as a physical in-store sighting.
    assert c.get('/api/stores/1/shelf',headers=h).json()['items']==[]
    mixed=c.get(f'/api/retail/baskets/{bid}/summary?chain=Carrefour',headers=h).json()
    assert mixed['estimated_total_cents'] is None and mixed['missing_count']==1
    c.post(f'/api/baskets/{bid}/free-items',json={'title':'Pan','quantity':1},headers=h)
    incomplete=c.get(f'/api/retail/baskets/{bid}/summary?chain=DIA',headers=h).json()
    assert incomplete['estimated_total_cents'] is None

def test_product_search_not_available_without_user_agent(env):
    c,login=env;h=login()
    assert c.get('/api/food/search?q=leche',headers=h).status_code==503
    assert c.get('/api/food/search?q=a',headers=h).status_code==422
    assert c.get('/api/food/search?q=leche').status_code==401

def test_dynamic_off_results_are_labelled_and_cached(env,monkeypatch):
    import main
    c,login=env;h=login();monkeypatch.setenv('SHOPPER_OFF_USER_AGENT','SHOPPER/10.0 (contact@example.org)')
    main._OFF_SEARCH_CACHE.clear();main._OFF_SEARCH_TIMES.clear()
    calls=[]
    class Fake:
        def __init__(self): self.content=json.dumps({'products':[{'code':'3017620422003','product_name':'Nutella',
            'brands':'Nutella','quantity':'400 g','image_front_small_url':'https://images.openfoodfacts.org/images/products/a.jpg'}]}).encode()
        def __enter__(self):return self
        def __exit__(self,*x):pass
        def read(self,n):return self.content[:n]
    def fake(req,timeout=8):
        calls.append(req.full_url)
        assert 'search_terms=nutella' in req.full_url
        assert req.headers['User-agent'].startswith('SHOPPER/')
        return Fake()
    monkeypatch.setattr(main.urllib.request,'urlopen',fake)
    r=c.get('/api/food/search?q=Nutella',headers=h)
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['name']=='Nutella'
    assert 'no precio' in r.json()['notice'].lower()
    assert c.get('/api/food/search?q=nutella',headers=h).status_code==200
    assert len(calls)==1

def test_store_access_does_not_leak_user_data_to_guests(env):
    c,login=env
    assert c.get('/api/bootstrap').status_code==401
    assert c.get('/api/retail/catalog').status_code==200
    assert c.get('/').status_code==200
    assert 'SHOPPER · Compra mejor' in c.get('/v10').text
    assert c.get('/classic').status_code==200
    assert c.get('/static/v10.js').status_code==200
    assert c.get('/static/v10.css').status_code==200
