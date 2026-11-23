"""SHOPPER 11: dependent selectors, basket-context isolation, privacy-first help."""
from .conftest import create_basket


def _place(c,h,name):
    r=c.post('/api/places',headers=h,json={'name':name})
    assert r.status_code==200,r.text
    return r.json()['id']


def _link(c,h,pid,sid):
    r=c.post(f'/api/places/{pid}/stores',headers=h,json={'store_id':sid,'save':True})
    assert r.status_code==200,r.text


def test_dependent_basket_form_and_multi_select(env):
    c,login=env;h=login()
    home=_place(c,h,'Casa');office=_place(c,h,'Oficina')
    _link(c,h,home,1);_link(c,h,home,2);_link(c,h,office,2)
    standard={'title':'Recados de casa','kind':'semanal','place_id':home,
        'topics':['frescos','limpieza'],'preferred_store_ids':[1,2],
        'accent':'ocean','cover_emoji':'🥑'}
    bad=c.post('/api/baskets',json={**standard,'event_on':'2026-12-20'},headers=h)
    assert bad.status_code==400 and 'solo' in bad.json()['detail'].lower()
    bad=c.post('/api/baskets',json={**standard,'preferred_store_ids':[1,1]},headers=h)
    assert bad.status_code==400
    bad=c.post('/api/baskets',json={**standard,'topics':['frescos','frescos']},headers=h)
    assert bad.status_code==400
    good=c.post('/api/baskets',json=standard,headers=h)
    assert good.status_code==200,good.text
    bid=good.json()['id']
    d=c.get(f'/api/baskets/{bid}',headers=h).json()
    assert d['preferred_store_ids']==[1,2] and d['topics']==['frescos','limpieza']
    assert d['basket']['cover_emoji']=='🥑' and d['basket']['accent']=='ocean'
    assert d['basket']['event_on'] is None
    # Changing place invalidates previous store selection, not other metadata.
    upd=c.patch(f'/api/baskets/{bid}',json={'place_id':office},headers=h)
    assert upd.status_code==200,upd.text
    d=c.get(f'/api/baskets/{bid}',headers=h).json()
    assert d['preferred_store_ids']==[]
    assert c.patch(f'/api/baskets/{bid}',json={'preferred_store_ids':[1]},headers=h).status_code==400
    assert c.patch(f'/api/baskets/{bid}',json={'preferred_store_ids':[2]},headers=h).status_code==200
    # Event date only appears for event baskets.
    assert c.patch(f'/api/baskets/{bid}',json={'event_on':'2026-12-20'},headers=h).status_code==400
    assert c.patch(f'/api/baskets/{bid}',json={'kind':'evento','event_on':'2026-12-20'},headers=h).status_code==200
    assert c.patch(f'/api/baskets/{bid}',json={'kind':'mensual'},headers=h).status_code==200
    assert c.get(f'/api/baskets/{bid}',headers=h).json()['basket']['event_on'] is None


def test_store_network_catalog_and_context_do_not_claim_stock(env):
    c,login=env;h=login()
    p=_place(c,h,'Casa norte');_link(c,h,p,1)
    r=c.get(f'/api/places/{p}/retail',headers=h)
    assert r.status_code==200,r.text
    j=r.json()
    assert j['total']>0 and all(x['chain']=='DIA' for x in j['items'])
    assert 'no inventario' in j['data_scope'].lower()
    b=c.post('/api/baskets',headers=h,json={'title':'Compra norte','kind':'ocasional','place_id':p,'preferred_store_ids':[1]}).json()['id']
    assert c.get(f'/api/baskets/{b}/shopping-context',headers=h).json()['chains'][0]['chain']=='DIA'
    h2=login('lucas_demo')
    assert c.get(f'/api/places/{p}/retail',headers=h2).status_code==403
    assert c.get(f'/api/baskets/{b}/shopping-context',headers=h2).status_code==403


def test_event_duplicate_does_not_carry_wrong_date(env):
    c,login=env;h=login()
    b=c.post('/api/baskets',headers=h,json={'title':'Comida de amigos','kind':'evento','event_on':'2026-12-20'}).json()['id']
    clone=c.post(f'/api/baskets/{b}/duplicate',headers=h)
    assert clone.status_code==200,clone.text
    d=c.get(f"/api/baskets/{clone.json()['id']}",headers=h).json()['basket']
    assert d['kind']=='ocasional' and d['event_on'] is None


def test_help_only_accepted_friends_and_owner_actions(env):
    c,login=env;ha=login()
    b=create_basket(c,ha)
    r=c.post('/api/circle/help',headers=ha,json={'area_label':'Madrid norte','note':'¿Alguien puede traerme leche?','basket_id':b})
    assert r.status_code==200,r.text
    hid=r.json()['id']
    h2=login('lucas_demo')
    assert c.get('/api/circle/help',headers=h2).json()['items']==[]
    assert c.post(f'/api/circle/help/{hid}/action',json={'action':'accept'},headers=h2).status_code==403
    # Accept mutually trusted invite, then request becomes visible.
    r=c.post('/api/friends/invite',headers=ha);code=r.json()['code']
    assert c.post('/api/invitations/redeem',headers=h2,json={'code':code}).status_code==200
    assert len(c.get('/api/circle/help',headers=h2).json()['items'])==1
    assert c.post(f'/api/circle/help/{hid}/action',json={'action':'accept'},headers=h2).status_code==200
    assert c.post(f'/api/circle/help/{hid}/action',json={'action':'accept'},headers=h2).status_code==409
    assert c.post(f'/api/circle/help/{hid}/action',json={'action':'done'},headers=ha).status_code==200
    assert c.post('/api/circle/help',headers=ha,json={'area_label':'Avenida 55 piso 5','note':'Necesito pan'}).status_code==400


def test_v11_frontend_loaded_and_prior_versions_retained(env):
    c,login=env
    assert c.get('/health').json()['version']=='13.0'
    assert c.get('/').status_code==200
    assert '/static/v11.js' in c.get('/v11').text
    assert c.get('/static/v11.js').status_code==200
    assert c.get('/static/v11.css').status_code==200
    assert c.get('/previous').status_code==200
    assert c.get('/classic').status_code==200


def test_help_does_not_leak_private_basket_name_to_friend(env):
    c,login=env;h=login();bid=c.post('/api/baskets',headers=h,json={'title':'Cesta privada con información sensible','kind':'ocasional'}).json()['id']
    req=c.post('/api/circle/help',headers=h,json={'area_label':'Madrid norte','note':'¿Me podéis traer pan?','basket_id':bid})
    assert req.status_code==200,req.text
    invite=c.post('/api/friends/invite',headers=h).json()['code']
    hb=login('lucas_demo')
    assert c.post('/api/invitations/redeem',headers=hb,json={'code':invite}).status_code==200
    visible=c.get('/api/circle/help',headers=hb).json()['items']
    assert len(visible)==1 and visible[0]['basket_title'] is None
    assert c.get('/api/circle/help',headers=h).json()['items'][0]['basket_title']=='Cesta privada con información sensible'
    assert c.post('/api/circle/help',headers=h,json={'area_label':'Madrid norte','note':'Vivo en calle Mayor 14 y necesito pan'}).status_code==400


def test_original_database_migration_preserves_baskets(tmp_path,monkeypatch):
    import sqlite3,importlib,db
    old=tmp_path/'existing_v10.sqlite3'
    with sqlite3.connect(old) as c:
        c.execute('''CREATE TABLE baskets(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,title TEXT NOT NULL,
           kind TEXT NOT NULL,place_id INTEGER,event_on TEXT,budget_cents INTEGER,notes TEXT NOT NULL DEFAULT '',
           created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
        c.execute("INSERT INTO baskets(id,owner_id,title,kind,created_at,updated_at) VALUES (1,1,'Mi cesta antigua','semanal','2026-01-01','2026-01-01')")
    monkeypatch.setenv('SHOPPER_DB',str(old))
    importlib.reload(db);db.init()
    with db.connect() as c:
        row=c.execute('SELECT * FROM baskets WHERE id=1').fetchone()
        assert row['title']=='Mi cesta antigua' and row['cover_emoji']=='🧺' and row['topics_json']=='[]'
