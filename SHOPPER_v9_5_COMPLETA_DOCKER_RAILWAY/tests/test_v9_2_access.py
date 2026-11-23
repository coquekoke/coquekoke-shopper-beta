"""Regression tests for simple LAN and cloud fail-closed deployment modes."""
import os, sys, importlib, subprocess
from pathlib import Path
from fastapi.testclient import TestClient


def test_lan_private_signup_and_origin(tmp_path, monkeypatch):
    monkeypatch.setenv('SHOPPER_DB', str(tmp_path / 'lan.sqlite3'))
    monkeypatch.setenv('SHOPPER_LAN', '1')
    monkeypatch.setenv('SHOPPER_REMOTE','0')
    monkeypatch.setenv('SHOPPER_DEMO','0')
    monkeypatch.setenv('SHOPPER_CSRF_KEY','a'*64)
    monkeypatch.setenv('SHOPPER_SIGNUP_CODE','my-private-lan-code-for-family')
    monkeypatch.setenv('SHOPPER_ALLOWED_HOSTS','192.168.1.25')
    parent=str(Path(__file__).resolve().parents[1]);
    if parent not in sys.path: sys.path.insert(0,parent)
    import db, main
    importlib.reload(db); importlib.reload(main)
    c=TestClient(main.app,base_url='http://192.168.1.25')
    wrong={'username':'a_user','display_name':'Ana','password':'TestPasswordLong123!','signup_code':'wrong'}
    assert c.post('/api/auth/register',headers={'Origin':'http://192.168.1.25'},json=wrong).status_code==403
    ok=dict(wrong,signup_code='my-private-lan-code-for-family')
    r=c.post('/api/auth/register',headers={'Origin':'http://192.168.1.25'},json=ok)
    assert r.status_code==200,r.text
    assert r.json()['token'] is None
    assert c.get('/api/config').json()['signup_code_required'] is True
    assert c.get('/api/me').status_code==200
    csrf=r.json()['csrf']
    assert c.post('/api/baskets',headers={'Origin':'http://192.168.1.25'},json={'title':'Fiesta','kind':'evento'}).status_code==403
    assert c.post('/api/baskets',headers={'Origin':'http://192.168.1.25','X-Shopper-CSRF':csrf},json={'title':'Fiesta','kind':'evento'}).status_code==200
    assert c.post('/api/baskets',headers={'Origin':'http://evil.test','X-Shopper-CSRF':csrf},json={'title':'Fiesta','kind':'evento'}).status_code==403


def test_cloud_volume_guard_no_volume(tmp_path):
    repo=Path(__file__).resolve().parents[1]
    env={**os.environ,'SHOPPER_REMOTE':'1','SHOPPER_DEMO':'0','SHOPPER_CSRF_KEY':'a'*64,'SHOPPER_SIGNUP_CODE':'some-long-private-signup-code','SHOPPER_DB':str(tmp_path/'no-volume.sqlite3'),'SHOPPER_REQUIRE_VOLUME':'1'}
    env.pop('RAILWAY_VOLUME_MOUNT_PATH',None)
    r=subprocess.run([sys.executable,'-c','import main'],cwd=repo,env=env,capture_output=True,text=True)
    assert r.returncode!=0
    assert 'Falta un volumen persistente Railway' in r.stderr
    assert not (tmp_path/'no-volume.sqlite3').exists()


def test_cloud_volume_guard_outside_path(tmp_path):
    repo=Path(__file__).resolve().parents[1]
    vol=tmp_path/'volume'; vol.mkdir()
    env={**os.environ,'SHOPPER_REMOTE':'1','SHOPPER_DEMO':'0','SHOPPER_CSRF_KEY':'a'*64,'SHOPPER_SIGNUP_CODE':'some-long-private-signup-code','SHOPPER_DB':str(tmp_path/'outside.sqlite3'),'SHOPPER_REQUIRE_VOLUME':'1','RAILWAY_VOLUME_MOUNT_PATH':str(vol)}
    r=subprocess.run([sys.executable,'-c','import main'],cwd=repo,env=env,capture_output=True,text=True)
    assert r.returncode!=0
    assert 'SHOPPER_DB debe estar dentro' in r.stderr
    assert not (tmp_path/'outside.sqlite3').exists()


def test_railway_requires_private_mode_and_volume(tmp_path):
    repo=Path(__file__).resolve().parents[1]
    base={**os.environ,'SHOPPER_DB':str(tmp_path/'railway.sqlite3'),'RAILWAY_ENVIRONMENT_NAME':'production'}
    base.pop('SHOPPER_REQUIRE_VOLUME',None)
    base.pop('SHOPPER_REMOTE',None)
    first=subprocess.run([sys.executable,'-c','import main'],cwd=repo,env=base,capture_output=True,text=True)
    assert first.returncode != 0
    assert 'SHOPPER_REMOTE=1 es obligatorio' in first.stderr
    base['SHOPPER_REMOTE']='1'
    second=subprocess.run([sys.executable,'-c','import main'],cwd=repo,env=base,capture_output=True,text=True)
    assert second.returncode != 0
    assert 'SHOPPER_REQUIRE_VOLUME=1 es obligatorio' in second.stderr
    assert not (tmp_path/'railway.sqlite3').exists()
