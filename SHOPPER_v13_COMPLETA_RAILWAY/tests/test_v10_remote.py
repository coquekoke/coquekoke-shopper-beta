import importlib
from fastapi.testclient import TestClient

def test_remote_registration_code_and_session(tmp_path,monkeypatch):
    monkeypatch.setenv('SHOPPER_REMOTE','1')
    monkeypatch.setenv('SHOPPER_DEMO','0')
    monkeypatch.setenv('SHOPPER_DB',str(tmp_path/'remote_v10.sqlite3'))
    monkeypatch.setenv('SHOPPER_CSRF_KEY','x'*40)
    monkeypatch.setenv('SHOPPER_SIGNUP_CODE','PrivateCodeForTesting2026')
    import db,main
    importlib.reload(db);importlib.reload(main)
    c=TestClient(main.app,base_url='https://testserver')
    assert c.get('/api/config').json()['signup_code_required'] is True
    fields={'username':'pruebav10','display_name':'Prueba','password':'S3guraPrivada2026!'}
    r=c.post('/api/auth/register',json={**fields,'signup_code':'bad'},headers={'Origin':'https://testserver'})
    assert r.status_code==403 and 'Código privado incorrecto' in r.json()['detail']
    r=c.post('/api/auth/register',json={**fields,'signup_code':'PrivateCodeForTesting2026'},headers={'Origin':'https://testserver'})
    assert r.status_code==200,r.text
    assert c.get('/api/bootstrap').status_code==200
    assert c.get('/api/bootstrap').json()['baskets'][0]['title']=='Actual'
    assert c.get('/api/retail/catalog').status_code==200
