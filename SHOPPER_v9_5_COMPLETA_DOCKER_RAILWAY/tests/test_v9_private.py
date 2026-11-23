"""Private HTTPS beta / independent-device simulation.
Two TestClient instances represent distinct phones with separate cookies.
"""
import importlib, os, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def remote(tmp_path,monkeypatch):
    monkeypatch.setenv('SHOPPER_DB',str(tmp_path/'remote.sqlite3'))
    monkeypatch.setenv('SHOPPER_REMOTE','1')
    monkeypatch.setenv('SHOPPER_DEMO','0')
    monkeypatch.setenv('SHOPPER_CSRF_KEY','0'*64)
    monkeypatch.setenv('SHOPPER_SIGNUP_CODE','private-family-invite-very-secret')
    parent=str(Path(__file__).resolve().parents[1])
    if parent not in sys.path:sys.path.insert(0,parent)
    import db,main
    importlib.reload(db);importlib.reload(main)
    c1=TestClient(main.app,base_url='https://testserver')
    c2=TestClient(main.app,base_url='https://testserver')
    def sign(c,username):
        r=c.post('/api/auth/register',headers={'Origin':'https://testserver'},json={
          'username':username,'display_name':username.title(),
          'password':'ExtraSecurePassword2026!','signup_code':'private-family-invite-very-secret'})
        assert r.status_code==200,r.text
        assert not r.json()['token']
        assert c.cookies.get('shopper_session')
        return r.json()['csrf']
    return c1,c2,sign,main

def test_remote_cookie_csrf_and_private_signup(remote):
    a,b,sign,m=remote
    assert a.get('/api/bootstrap').status_code==401
    assert a.post('/api/auth/register',headers={'Origin':'https://testserver'},json={
        'username':'outsider','display_name':'Outsider','password':'ExtraSecurePassword2026!',
        'signup_code':'wrong'}).status_code==403
    ca=sign(a,'family_a')
    r=a.get('/api/bootstrap');assert r.status_code==200
    assert r.json()['me']['username']=='family_a'
    assert a.post('/api/baskets',json={'title':'Fiesta','kind':'evento'},headers={'Origin':'https://testserver'}).status_code==403
    assert a.post('/api/baskets',json={'title':'Fiesta','kind':'evento'},headers={
      'Origin':'https://outsider.net','X-Shopper-CSRF':ca}).status_code==403
    r=a.post('/api/baskets',json={'title':'Fiesta','kind':'evento'},headers={
      'Origin':'https://testserver','X-Shopper-CSRF':ca});assert r.status_code==200,r.text
    assert a.get('/api/baskets/'+str(r.json()['id'])).status_code==200
    assert a.get('/api/config').json()['demo_mode'] is False

def test_two_phones_shared_basket_task_and_revocation(remote):
    a,b,sign,m=remote
    ca=sign(a,'mother');cb=sign(b,'daughter')
    H1={'Origin':'https://testserver','X-Shopper-CSRF':ca}
    H2={'Origin':'https://testserver','X-Shopper-CSRF':cb}
    basket=a.post('/api/baskets',headers=H1,json={'title':'Para la abuela','kind':'semanal'}).json()['id']
    assert b.get(f'/api/baskets/{basket}').status_code==403
    invite=a.post(f'/api/baskets/{basket}/invite',headers=H1,json={'role':'editor'}).json()['code']
    assert b.post('/api/invitations/redeem',headers=H2,json={'code':invite}).status_code==200
    assert b.post('/api/invitations/redeem',headers=H2,json={'code':invite}).status_code!=200
    r=b.post(f'/api/baskets/{basket}/free-items',headers=H2,json={'title':'Pan integral','quantity':2})
    assert r.status_code==200,r.text
    assert any(i['name']=='Pan integral' for i in a.get(f'/api/baskets/{basket}').json()['items'])
    task=a.post('/api/family/tasks',headers=H1,json={'basket_id':basket,'title':'Llevar cesta a la abuela'})
    assert task.status_code==200,task.text
    tid=task.json()['id']
    assert any(x['id']==tid for x in b.get('/api/family/tasks').json())
    assert b.patch(f'/api/family/tasks/{tid}',headers=H2,json={'status':'accepted'}).status_code==200
    assert a.patch(f'/api/family/tasks/{tid}',headers=H1,json={'status':'done'}).status_code==403
    assert b.patch(f'/api/family/tasks/{tid}',headers=H2,json={'status':'done'}).status_code==200
    assert a.delete(f'/api/baskets/{basket}/members/2',headers=H1).status_code==200
    assert b.get(f'/api/baskets/{basket}').status_code==403
    assert all(x['id']!=tid for x in b.get('/api/family/tasks').json())

def test_change_password_invalidates_other_session(remote):
    a,b,sign,m=remote
    c=sign(a,'account_a')
    r=b.post('/api/auth/login',headers={'Origin':'https://testserver'},json={
      'username':'account_a','password':'ExtraSecurePassword2026!'})
    assert r.status_code==200
    r=a.post('/api/auth/change-password',headers={'Origin':'https://testserver','X-Shopper-CSRF':c},
      json={'current_password':'ExtraSecurePassword2026!','new_password':'NewEvenStronger2026!'})
    assert r.status_code==200,r.text
    assert b.get('/api/me').status_code==401
    assert a.get('/api/me').status_code==200

def test_remote_disables_bearer_and_requires_origin(remote):
    a,b,sign,m=remote
    csrf=sign(a,'bearer_test')
    cookie=a.cookies.get('shopper_session')
    b.headers['Authorization']='Bearer '+cookie
    assert b.get('/api/me').status_code==401
    assert a.post('/api/auth/logout',headers={'X-Shopper-CSRF':csrf}).status_code==403
    assert a.post('/api/auth/logout',headers={'Origin':'https://testserver','X-Shopper-CSRF':csrf}).status_code==200
    assert a.get('/api/me').status_code==401
