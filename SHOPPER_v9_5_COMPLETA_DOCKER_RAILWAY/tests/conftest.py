import importlib
import os,sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv('SHOPPER_DB',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('SHOPPER_DEMO','1')
    repo=str(Path(__file__).resolve().parents[1])
    if repo not in sys.path:sys.path.insert(0,repo)
    import db,main
    importlib.reload(db)
    importlib.reload(main)
    client=TestClient(main.app)
    def login(username='maria_demo',password='ShopperDemo2026!'):
        r=client.post('/api/auth/login',json={'username':username,'password':password})
        assert r.status_code==200,r.text
        # Legacy API tests deliberately use bearer headers, not browser cookies.
        client.cookies.clear()
        return {'Authorization':'Bearer '+r.json()['token']}
    return client,login

def create_basket(c,h,title='Cesta evento'):
    r=c.post('/api/baskets',json={'title':title,'kind':'evento'},headers=h)
    assert r.status_code==200,r.text
    return r.json()['id']
