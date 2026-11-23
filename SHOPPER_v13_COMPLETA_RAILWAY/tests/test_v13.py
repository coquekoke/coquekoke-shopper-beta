"""Cards, recipes and recipe-to-basket regression tests."""
from db import connect,one

def test_v13_health_and_assets(env):
    c,login=env
    assert c.get('/health').json()['version']=='13.0'
    assert c.get('/').status_code==200
    assert 'Recetas a cesta' in c.get('/').text
    assert c.get('/static/v13.js').status_code==200
    assert c.get('/static/v13.css').status_code==200
    assert c.get('/v12').status_code==200
    assert c.get('/api/v13/cards').status_code==401
    assert c.get('/api/v13/recipes').status_code==401


def test_private_card_encrypted_and_user_scoped(env):
    c,login=env;h=login()
    p={'chain':'Club DIA','label':'Mi carnet DIA','mode':'static','barcode_type':'EAN13','code':'4006381333931'}
    r=c.post('/api/v13/cards',json=p,headers=h)
    assert r.status_code==200,r.text
    id=r.json()['id']
    with connect() as db:
        row=one(db,'SELECT ciphertext,last_four FROM v13_loyalty_cards WHERE id=?',(id,))
        assert row['last_four']=='3931'
        assert row['ciphertext']!='4006381333931'
        assert '4006381333931' not in row['ciphertext']
    listed=c.get('/api/v13/cards',headers=h).json()['items']
    assert listed[0]['last_four']=='3931' and 'code' not in listed[0]
    r=c.get(f'/api/v13/cards/{id}/barcode.svg',headers=h)
    assert r.status_code==200 and '<svg' in r.text
    assert c.get(f'/api/v13/cards/{id}/reveal',headers=h).json()['code']==p['code']
    other=login('lucas_demo')
    assert c.get('/api/v13/cards',headers=other).json()['items']==[]
    assert c.get(f'/api/v13/cards/{id}/reveal',headers=other).status_code==404
    assert c.get(f'/api/v13/cards/{id}/barcode.svg',headers=other).status_code==404
    assert c.delete(f'/api/v13/cards/{id}',headers=other).status_code==404
    assert c.delete(f'/api/v13/cards/{id}',headers=h).status_code==200


def test_dynamic_card_and_invalid_barcode(env):
    c,login=env;h=login()
    static={'chain':'Lidl Plus','label':'Lidl','mode':'static','barcode_type':'QR','code':'FOO123'}
    assert c.post('/api/v13/cards',json=static,headers=h).status_code==400
    static.update(chain='Club Carrefour',barcode_type='EAN13',code='0000000000001')
    assert c.post('/api/v13/cards',json=static,headers=h).status_code==400
    static.update(code='4006381333931',official_url='http://invalid.example')
    assert c.post('/api/v13/cards',json=static,headers=h).status_code==400
    official={'chain':'Lidl Plus','label':'Lidl','mode':'official','official_url':'https://www.lidl.es/'}
    r=c.post('/api/v13/cards',json=official,headers=h)
    assert r.status_code==200,r.text
    id=r.json()['id']
    assert c.get(f'/api/v13/cards/{id}/barcode.svg',headers=h).status_code==400
    qr={'chain':'Otro','label':'Club privado','mode':'static','barcode_type':'QR','code':'ESTATICO-123'}
    k=c.post('/api/v13/cards',json=qr,headers=h)
    assert k.status_code==200,k.text
    assert 'svg' in c.get(f'/api/v13/cards/{k.json()["id"]}/barcode.svg',headers=h).headers['content-type']


def test_recipe_parse_compare_and_shared_basket(env):
    c,login=env;h=login()
    text='200 g de arroz\n250 ml leche entera\n2 huevos\n50 g harina'
    draft={'name':'Arroz con leche y huevo','servings':2,'ingredients_text':text}
    preview=c.post('/api/v13/recipes/analyze',headers=h,json=draft)
    assert preview.status_code==200,preview.text
    ing=preview.json()['ingredients'];assert len(ing)==4 and ing[0]['base_amount']==200
    r=c.post('/api/v13/recipes',headers=h,json=draft)
    assert r.status_code==200,r.text
    rid=r.json()['id']
    compare=c.post(f'/api/v13/recipes/{rid}/compare',headers=h,json={'servings':2}).json()
    by={x['chain']:x for x in compare['comparisons']}
    assert by['Carrefour']['covered']==3
    assert by['Carrefour']['complete'] is False
    assert by['Carrefour']['estimated_full_purchase_cents'] is None
    assert by['Carrefour']['known_subtotal_cents']>0
    assert by['DIA']['covered']==2
    match=by['Carrefour']['lines'][0]['match'];assert match['packs']>=1
    scaled=c.post(f'/api/v13/recipes/{rid}/compare',headers=h,json={'servings':4}).json()
    assert scaled['servings']==4
    choices=by['Carrefour']['lines'][0]['options']
    assert c.put(f'/api/v13/recipes/{rid}/choice',headers=h,json={'chain':'Carrefour','ingredient_index':0,'listing_id':choices[0]['listing_id']}).status_code==200
    assert c.put(f'/api/v13/recipes/{rid}/choice',headers=h,json={'chain':'Carrefour','ingredient_index':0,'listing_id':'evil'}).status_code==400
    user2=login('lucas_demo')
    assert c.get(f'/api/v13/recipes/{rid}',headers=user2).status_code==404
    assert c.post(f'/api/v13/recipes/{rid}/compare',headers=user2,json={'servings':2}).status_code==404
    b=c.post(f'/api/v13/recipes/{rid}/to-basket',headers=h,json={'chain':'Carrefour','servings':2})
    assert b.status_code==200,b.text
    bid=b.json()['basket_id']
    basket=c.get(f'/api/baskets/{bid}',headers=h).json()
    assert basket['basket']['kind']=='ocasional'
    assert 'arroz' in basket['basket']['title'].lower()
    assert b.json()['matched_lines']==3 and b.json()['unmatched_lines']==1
    assert c.get(f'/api/baskets/{bid}',headers=user2).status_code==403
    assert c.get('/api/v13/recipes',headers=user2).json()['items']==[]


def test_schema_org_and_bad_place(env):
    c,login=env;h=login()
    payload={'@context':'https://schema.org','@type':'Recipe','name':'Arroz de prueba',
       'recipeYield':'4 porciones','recipeIngredient':['250 g arroz','1 l leche']}
    r=c.post('/api/v13/recipes',headers=h,json={'name':'Arroz de prueba','servings':4,'ingredients_text':__import__('json').dumps(payload)})
    assert r.status_code==200,r.text
    rid=r.json()['id']
    assert c.post(f'/api/v13/recipes/{rid}/compare',headers=h,json={'servings':4,'place_id':9876}).status_code==404
    assert c.post(f'/api/v13/recipes/{rid}/to-basket',headers=h,json={'chain':'DIA','servings':4,'place_id':9876}).status_code==404
    p=c.post('/api/places',headers=h,json={'name':'Casa Madrid'}).json()['id']
    sid=c.post('/api/stores',headers=h,json={'name':'Mi tienda Lidl','chain':'Lidl','address':'Calle Madrid 123, Madrid, España'}).json()['id']
    assert c.post(f'/api/places/{p}/stores',headers=h,json={'store_id':sid,'save':True}).status_code == 200
    # Only chains in the selected location are shown; unpriced chain remains incomplete.
    assert c.post(f'/api/v13/recipes/{rid}/compare',headers=h,json={'servings':4,'place_id':p}).status_code==200


def test_recipe_parser_no_remote_fetch_or_fabricated_price(env):
    c,login=env;h=login()
    r=c.post('/api/v13/recipes',headers=h,json={'name':'Receta test','servings':2,'ingredients_text':'100 g de guisantes\n2 cucharadas de aceite de oliva','source_url':'https://ejemplo.com/receta'})
    assert r.status_code==200,r.text
    comparison=c.post(f'/api/v13/recipes/{r.json()["id"]}/compare',headers=h,json={'servings':2}).json()
    assert all(x['complete'] is False and x['estimated_full_purchase_cents'] is None for x in comparison['comparisons'])
    assert all(x['covered']<x['total'] for x in comparison['comparisons'])


def test_duplicate_ingredients_aggregate_whole_packages(env):
    c,login=env;h=login()
    r=c.post('/api/v13/recipes',headers=h,json={'name':'Doble arroz','servings':2,'ingredients_text':'200 g arroz\n300 g arroz'})
    assert r.status_code==200,r.text
    rid=r.json()['id']
    x=c.post(f'/api/v13/recipes/{rid}/compare',headers=h,json={'servings':2}).json()
    dia=next(c for c in x['comparisons'] if c['chain']=='DIA')
    assert dia['complete']
    assert len(dia['aggregate_items'])==1
    assert dia['aggregate_items'][0]['packs']==1
    b=c.post(f'/api/v13/recipes/{rid}/to-basket',headers=h,json={'chain':'DIA','servings':2})
    assert b.status_code==200
    basket=c.get('/api/baskets/'+str(b.json()['basket_id']),headers=h).json()
    assert len(basket['items'])==1 and basket['items'][0]['quantity']==1
