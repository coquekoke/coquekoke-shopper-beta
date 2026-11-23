"""SHOPPER 13: encrypted loyalty card wallet + recipe-to-basket comparison.

No retailer API access or real-time stock is implied. Recipes operate on a small,
source-dated editorial retail snapshot. No server-side arbitrary URL fetching.
"""
from __future__ import annotations
import base64, hashlib, hmac, io, json, math, os, re, unicodedata
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Literal
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet, InvalidToken
from reportlab.graphics.barcode import createBarcodeDrawing
import qrcode
import qrcode.image.svg
from db import ROOT, connect, many, one, now

DATA=json.loads((ROOT/'data'/'retail_official_snapshot_2026-11-23.json').read_text('utf-8'))
DDL='''
CREATE TABLE IF NOT EXISTS v13_loyalty_cards(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 chain TEXT NOT NULL, label TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode IN ('static','official')),
 barcode_type TEXT, ciphertext TEXT, last_four TEXT,
 official_url TEXT, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_v13_cards_owner ON v13_loyalty_cards(user_id,id);
CREATE TABLE IF NOT EXISTS v13_recipes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, source_url TEXT, source_type TEXT NOT NULL,
 servings INTEGER NOT NULL, raw_text TEXT NOT NULL,
 ingredients_json TEXT NOT NULL, overrides_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_v13_recipes_owner ON v13_recipes(user_id,id);
'''

def migrate():
    with connect() as db:db.executescript(DDL)

DYNAMIC={'Lidl Plus'}
PRESETS=[
 {'chain':'Club DIA','mode':'official','url':'https://www.dia.es/'},
 {'chain':'Club Carrefour','mode':'official','url':'https://www.carrefour.es/clubcarrefour/'},
 {'chain':'Lidl Plus','mode':'official','url':'https://www.lidl.es/'},
 {'chain':'Club Alcampo','mode':'official','url':'https://www.compraonline.alcampo.es/'},
 {'chain':'Otros supermercados','mode':'static','url':''}
]

def cipher():
    # Key separation via HMAC: avoid deriving a Fernet key directly from the public version.
    # The cloud beta already has a 32+-character secret; a dedicated card secret is preferred.
    key=os.getenv('SHOPPER_CARDS_KEY') or os.getenv('SHOPPER_CSRF_KEY','shopper-local-dev-secret-do-not-use-on-internet')
    digest=hmac.new(key.encode(),b'SHOPPER-LOYALTY-ENCRYPTION-V13',hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

class CardIn(BaseModel):
    chain:str=Field(min_length=2,max_length=60)
    label:str=Field(min_length=2,max_length=80)
    mode:Literal['static','official']
    barcode_type:Literal['EAN13','CODE128','QR']|None=None
    code:str|None=Field(default=None,max_length=180)
    official_url:str|None=Field(default=None,max_length=300)
    notes:str=Field(default='',max_length=200)

def ean13_valid(s):
    if len(s)!=13 or not s.isdigit():return False
    ck=(10-(sum(int(s[i])*(1 if i%2==0 else 3) for i in range(12))%10))%10
    return ck==int(s[12])

def normalize_url(s):
    if not s:return None
    p=urlparse(s)
    if p.scheme!='https' or not p.netloc or p.username or p.password or len(s)>300:
        raise HTTPException(400,'Utiliza una dirección HTTPS oficial, sin credenciales')
    return s

def validate_card(d):
    link=normalize_url(d.official_url)
    if d.mode=='official':
        if not link:raise HTTPException(400,'Añade un enlace HTTPS al programa oficial')
        return None,None,None,link
    if d.chain.strip().casefold() in {x.casefold() for x in DYNAMIC}:
        raise HTTPException(400,'Este programa utiliza códigos que pueden cambiar: abre la aplicación oficial')
    value=(d.code or '').strip()
    if not value or len(value)>180 or any(ord(c)<32 for c in value):raise HTTPException(400,'Código estático incorrecto')
    if not d.barcode_type:raise HTTPException(400,'Elige un formato de código')
    if d.barcode_type=='EAN13' and not ean13_valid(value):
        raise HTTPException(400,'EAN-13 requiere 13 cifras con dígito de control correcto')
    if d.barcode_type=='CODE128' and (not value.isascii() or not value.isprintable()):
        raise HTTPException(400,'CODE128 requiere caracteres ASCII imprimibles')
    return d.barcode_type,cipher().encrypt(value.encode()).decode(),value[-4:],link

def card_public(row):
    return {k:row[k] for k in ('id','chain','label','mode','barcode_type','last_four','official_url','notes','created_at','updated_at')}

def own_card(db,uid,cid):
    row=one(db,'SELECT * FROM v13_loyalty_cards WHERE id=? AND user_id=?',(cid,uid))
    if not row:raise HTTPException(404,'Tarjeta no encontrada')
    return row

def own_recipe(db,uid,rid):
    row=one(db,'SELECT * FROM v13_recipes WHERE id=? AND user_id=?',(rid,uid))
    if not row:raise HTTPException(404,'Receta no encontrada')
    return row

def deaccent(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(s).lower()) if not unicodedata.combining(c))

UNITS={'kg':('g',1000),'kilos':('g',1000),'kilo':('g',1000),'g':('g',1),'gr':('g',1),'gramos':('g',1),
       'l':('ml',1000),'litro':('ml',1000),'litros':('ml',1000),'ml':('ml',1),
       'ud':('ud',1),'uds':('ud',1),'unidad':('ud',1),'unidades':('ud',1),
       'cucharada':('cda',1),'cucharadas':('cda',1),'cucharadita':('cdta',1),'cucharaditas':('cdta',1),
       'taza':('taza',1),'tazas':('taza',1)}
FRACTIONS={'½':'.5','¼':'.25','¾':'.75'}

def number(s):
    s=str(s)
    if s in FRACTIONS:return float(FRACTIONS[s])
    if '/' in s:
        a,b=s.split('/',1)
        return float(a)/float(b)
    return float(s.replace(',','.'))

PREFIX=re.compile(r'^\s*(\d+(?:[.,]\d+)?|\d+\s*/\s*\d+|[½¼¾])\s*(kg|kilos?|g|gr|gramos?|ml|l|litros?|uds?\.?|unidades?|cucharadas?|cucharaditas?|tazas?)?\s*(?:de\s+)?(.+?)\s*$',re.I)
SUFFIX=re.compile(r'^(.+?)\s+(\d+(?:[.,]\d+)?|\d+/\d+)\s*(kg|g|gr|ml|l|ud|uds?|unidades?)\s*$',re.I)

def parse_one(raw):
    s=str(raw).strip().strip('-•*·\t ').strip()
    if not s:return None
    s=re.sub(r'^\d+[.)]\s+','',s)
    s=re.sub(r'\s+',' ',s)
    m=PREFIX.match(s)
    if m:
        qty=number(m.group(1)); unit=(m.group(2) or 'ud').strip('.').lower(); name=m.group(3).strip()
    else:
        m=SUFFIX.match(s)
        if m:qty=number(m.group(2));unit=m.group(3).lower();name=m.group(1).strip()
        else:qty=1.0;unit='ud';name=s
    name=re.sub(r'^de\s+','',name,flags=re.I).strip(' ,.;:')
    if not name or not (0<qty<100000):return None
    base,multi=UNITS.get(unit,('ud',1))
    return {'raw':s,'name':name[:120],'amount':qty,'unit':unit,
            'base_amount':round(qty*multi,3),'base_unit':base,'quantity_uncertain':not bool(m)}

SKIP=re.compile(r'^(ingredientes?|preparaci[oó]n|elaboraci[oó]n|instrucciones?|pasos?|modo de preparaci[oó]n|tiempo|calor[ií]as)\s*:?$',re.I)

def discover_recipe_json(raw):
    try: obj=json.loads(raw)
    except Exception:return None
    def walk(x):
        if isinstance(x,list):
            for v in x:
                found=walk(v)
                if found:return found
        if isinstance(x,dict):
            tp=x.get('@type',[]);tp=[tp] if isinstance(tp,str) else tp
            if 'Recipe' in tp and isinstance(x.get('recipeIngredient'),list):return x
            for k in ('@graph','mainEntity','recipe'):
                if k in x:
                    found=walk(x[k])
                    if found:return found
        return None
    return walk(obj)

def parse_recipe(text):
    src=discover_recipe_json(text)
    lines=src['recipeIngredient'] if src else text.splitlines()
    parsed=[]
    for line in lines:
        if not isinstance(line,str):continue
        s=line.strip()
        if not s or SKIP.fullmatch(s) or s.startswith('#'):continue
        item=parse_one(s)
        if item:parsed.append(item)
        if len(parsed)>80:raise HTTPException(400,'Máximo 80 ingredientes')
    if not parsed:raise HTTPException(400,'No se encontraron ingredientes; pégalos uno por línea')
    return parsed, {'name':str(src.get('name',''))[:100] if src else None,'servings':src.get('recipeYield') if src else None,'is_schema_org':bool(src)}

# High-precision lexical comparison. Never infer allergen-safe equivalence.
CORE={'arroz':['arroz'],'leche':['leche'],'huevo':['huevo','huevos'],'huevos':['huevo','huevos'],
      'aceite':['aceite'],'harina':['harina'],'tomate':['tomate','tomates'],'tomates':['tomate','tomates'],
      'pollo':['pollo'],'sal':['sal'],'pan':['pan'],'azucar':['azucar'],'mantequilla':['mantequilla']}
QUALIFIERS=['sin lactosa','sin gluten','integral','basmati','semidesnatada','desnatada','entera','fresca','largo','redondo','ecologica','ecologico']

def core_of(text):
    words=re.findall(r'[a-z]+',deaccent(text))
    for w in words:
        if w in CORE:return w
    return None

def pack_size(fmt):
    f=deaccent(fmt).replace(',','.')
    m=re.search(r'(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l|uds?|ud\.?)(?!\w)',f)
    if m:
        mult=int(m.group(1)); amount=float(m.group(2)); u=m.group(3).strip('.')
    else:
        m=re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|ml|l|uds?|ud\.?)(?!\w)',f)
        if not m:return None,None
        mult=1; amount=float(m.group(1)); u=m.group(2).strip('.')
    v=amount*mult
    base,factor=UNITS.get(u,(None,1))
    return (round(v*factor,2),base)

def candidates(ing,chain,over=None):
    core=core_of(ing['name']); normal=deaccent(ing['name']); out=[]
    if not core:return out
    words=re.findall(r'[a-z]+',normal)
    qualifier=[q for q in QUALIFIERS if q in normal]
    for listing in DATA['items']:
        if listing['chain'].casefold()!=chain.casefold():continue
        title=deaccent(listing['name'])
        if not any(re.search(r'\b'+re.escape(c)+r'\b',title) for c in CORE[core]):continue
        if core=='arroz' and any(w in title for w in ('vasos','tres delicias','al punto')):continue
        qlist=[q for q in QUALIFIERS if q in title]
        if any(q not in qlist for q in qualifier):
            # Potentially unsafe substitutions are not automatic suggestions.
            continue
        # Different milk/rice types are deliberately NOT a default match.
        axes=[['sin lactosa'],['integral'],['basmati'],['semidesnatada','desnatada','entera']]
        conflict=False
        for group in axes:
            wanted=set(group)&set(qualifier); actual=set(group)&set(qlist)
            if wanted and actual!=wanted:conflict=True
        if conflict:continue
        size,unit=pack_size(listing.get('format',''))
        required=float(ing['base_amount'])
        compatible=unit==ing['base_unit'] and size and required>0
        packs=max(1,math.ceil(required/size)) if compatible else 1
        overlap=len(set(words)&set(re.findall(r'[a-z]+',title)))
        # If unit is unknown (e.g. a handful), displayed estimate is still one pack, explicitly unquantified.
        out.append({'listing_id':listing['id'],'name':listing['name'],'brand':listing['brand'],
                    'price_cents':listing['price_cents'],'unit_size':size,'unit':unit,
                    'packs':packs,'subtotal_cents':packs*listing['price_cents'],
                    'quantity_comparable':bool(compatible),'match_type':'aproximado' if not qualifier and overlap<2 else 'compatible',
                    'source_url':listing['source_url'],'observed_on':listing['observed_on'],
                    'product_id':None,'format':listing['format'],'score':overlap})
    return sorted(out,key=lambda a:(not a['quantity_comparable'],a['subtotal_cents'], -a['score']))[:8]

def substitute_candidates(ing,chain):
    # Only similar product families, never automatic and never for dietary exclusions.
    normal=deaccent(ing['name'])
    if any(term in normal for term in ('sin lactosa','sin gluten','alergia','alergeno')):
        return []
    core=core_of(normal)
    if not core:return []
    regular={x['listing_id'] for x in candidates(ing,chain)}
    result=[]
    for listing in DATA['items']:
        if listing['chain'].casefold()!=chain.casefold() or listing['id'] in regular:continue
        title=deaccent(listing['name'])
        if not any(re.search(r'\b'+re.escape(c)+r'\b',title) for c in CORE[core]):continue
        if core=='arroz' and any(w in title for w in ('vasos','tres delicias','al punto')):continue
        size,unit=pack_size(listing.get('format',''))
        compatible=unit==ing['base_unit'] and size and ing['base_amount']>0
        packs=max(1,math.ceil(ing['base_amount']/size)) if compatible else 1
        result.append({'listing_id':listing['id'],'name':listing['name'],'price_cents':listing['price_cents'],
          'packs':packs,'subtotal_cents':packs*listing['price_cents'],'unit_size':size,'unit':unit,
          'quantity_comparable':bool(compatible),'requires_confirmation':True,
          'note':'Sustitución de tipo o formato; revisa requisitos dietéticos, alérgenos y sabor'})
    return sorted(result,key=lambda x:(not x['quantity_comparable'],x['subtotal_cents']))[:4]

def recipe_compare(recipe,place=None,selected_chains=None):
    lines=json.loads(recipe['ingredients_json'])
    portions=int(recipe['servings'])
    selected=int(recipe.get('requested_servings') or portions)
    factor=selected/portions
    ingredients=[{**x,'base_amount':round(x['base_amount']*factor,3),
                  'amount':round(x['amount']*factor,3)} for x in lines]
    bychain=[]
    chains=selected_chains or sorted({x['chain'] for x in DATA['items']})
    mapping=recipe.get('mapping') or {}
    for chain in chains:
        detail=[];known=0;subtotal=0
        for i,ing in enumerate(ingredients):
            choices=candidates(ing,chain)
            alternatives=substitute_candidates(ing,chain)
            override=mapping.get(f'{chain}:{i}')
            chosen=next((v for v in choices+alternatives if v['listing_id']==override),None) if override else (choices[0] if choices else None)
            if chosen:
                known+=1;subtotal+=chosen['subtotal_cents']
            detail.append({'ingredient_index':i,'ingredient':ing,'match':chosen,'options':choices,
                           'alternatives':alternatives,'missing':chosen is None})
        # Combine the same selected SKU across repeated ingredient lines: 200g + 300g rice
        # may require only one 1kg bag, not two separate bags.
        groups={}
        for item in detail:
            match=item['match']
            if not match:continue
            key=match['listing_id']
            if key not in groups:
                groups[key]={**match,'requested_base_amount':0,'lines':0,'pack_floor':0}
            g=groups[key];g['lines']+=1
            if match.get('quantity_comparable') and match.get('unit_size'):
                g['requested_base_amount']+=item['ingredient']['base_amount']
            else:g['pack_floor']+=1
        for g in groups.values():
            measured=math.ceil(g['requested_base_amount']/g['unit_size']) if g.get('unit_size') and g['requested_base_amount'] else 0
            g['packs']=max(1,measured+g['pack_floor'])
            g['subtotal_cents']=g['packs']*g['price_cents']
        subtotal=sum(x['subtotal_cents'] for x in groups.values())
        complete=known==len(ingredients) and all(x['match'] and x['match'].get('quantity_comparable') and not x['ingredient'].get('quantity_uncertain') for x in detail)
        bychain.append({'chain':chain,'lines':detail,'aggregate_items':list(groups.values()),'covered':known,'total':len(ingredients),
                        'known_subtotal_cents':subtotal,'estimated_full_purchase_cents':subtotal if complete else None,
                        'complete':complete,'has_uncertain_quantities':any(x['match'] and (not x['match'].get('quantity_comparable') or x['ingredient'].get('quantity_uncertain')) for x in detail),'has_snapshot':chain in {x['chain'] for x in DATA['items']}})
    return {'id':recipe.get('id'),'name':recipe['name'],'servings':selected,'base_servings':portions,
            'source_url':recipe.get('source_url'),'ingredients':ingredients,'comparisons':bychain,
            'snapshot_date':DATA['capture_date'],
            'notice':'Precios de muestra web del 23/11/2026. Se calcula la COMPRA de envases completos (no solo la porción usada); posibles faltantes significan total no calculable. Sin garantía de stock ni precio en tienda física. Revisa siempre alternativas, ingredientes y alérgenos.'}

class RecipeIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    servings:int=Field(default=2,ge=1,le=100)
    ingredients_text:str=Field(min_length=3,max_length=12000)
    source_url:str|None=Field(default=None,max_length=300)

class RecipeScale(BaseModel):
    servings:int=Field(ge=1,le=100)
    place_id:int|None=None

class Choice(BaseModel):
    chain:str=Field(min_length=2,max_length=70)
    ingredient_index:int=Field(ge=0,le=79)
    listing_id:str|None=None
    confirm_alternative:bool=False

class Convert(BaseModel):
    chain:str=Field(min_length=2,max_length=70)
    servings:int=Field(ge=1,le=100)
    place_id:int|None=None


def install(app,auth):
    migrate()

    @app.get('/api/v13/cards')
    def cards(user=Depends(auth)):
        with connect() as db:rows=many(db,'SELECT * FROM v13_loyalty_cards WHERE user_id=? ORDER BY id DESC',(user['id'],))
        return {'items':[card_public(x) for x in rows],'presets':PRESETS,'storage':'Código cifrado en el servidor; solo se revela con sesión autenticada. No guardar contraseñas ni códigos dinámicos.'}

    @app.post('/api/v13/cards')
    def create_card(d:CardIn,user=Depends(auth)):
        typ,encrypted,mask,link=validate_card(d)
        with connect() as db:
            c=db.execute('''INSERT INTO v13_loyalty_cards(user_id,chain,label,mode,barcode_type,ciphertext,last_four,official_url,notes,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(user['id'],d.chain.strip(),d.label.strip(),d.mode,typ,encrypted,mask,link,d.notes.strip(),now(),now()))
            return {'id':c.lastrowid,'saved':True}

    @app.delete('/api/v13/cards/{cid}')
    def delete_card(cid:int,user=Depends(auth)):
        with connect() as db:
            own_card(db,user['id'],cid)
            db.execute('DELETE FROM v13_loyalty_cards WHERE id=?',(cid,))
        return {'ok':True}

    @app.get('/api/v13/cards/{cid}/reveal')
    def reveal(cid:int,user=Depends(auth)):
        with connect() as db:row=own_card(db,user['id'],cid)
        if row['mode']!='static':raise HTTPException(400,'Abre la app oficial para consultar tu código dinámico')
        try:value=cipher().decrypt(row['ciphertext'].encode()).decode()
        except InvalidToken:raise HTTPException(409,'No se puede descifrar la tarjeta: comprueba SHOPPER_CARDS_KEY')
        return Response(content=json.dumps({'code':value,'barcode_type':row['barcode_type']}),media_type='application/json',headers={'Cache-Control':'no-store'})

    @app.get('/api/v13/cards/{cid}/barcode.svg')
    def barcode_image(cid:int,user=Depends(auth)):
        with connect() as db:row=own_card(db,user['id'],cid)
        if row['mode']!='static':raise HTTPException(400,'No es un código estático')
        try:code=cipher().decrypt(row['ciphertext'].encode()).decode()
        except InvalidToken:raise HTTPException(409,'Código no descifrable; clave de cifrado modificada')
        if row['barcode_type']=='QR':
            img=qrcode.make(code,image_factory=qrcode.image.svg.SvgPathImage,box_size=8,border=3)
            out=img.to_string()
        else:
            kind='EAN13' if row['barcode_type']=='EAN13' else 'Code128'
            out=createBarcodeDrawing(kind,value=code,barHeight=72,humanReadable=True).asString('svg')
        return Response(content=out,media_type='image/svg+xml',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @app.post('/api/v13/recipes/analyze')
    def analyze(d:RecipeIn,user=Depends(auth)):
        lines,info=parse_recipe(d.ingredients_text)
        return {'ingredients':lines,'suggested_name':info['name'],'schema_org':info['is_schema_org'],
                'preview':recipe_compare({'name':d.name,'servings':d.servings,'ingredients_json':json.dumps(lines)})}

    @app.get('/api/v13/recipes')
    def list_recipes(user=Depends(auth)):
        with connect() as db:rs=many(db,'SELECT id,name,servings,source_url,source_type,ingredients_json,created_at FROM v13_recipes WHERE user_id=? ORDER BY id DESC',(user['id'],))
        return {'items':[{'id':r['id'],'name':r['name'],'servings':r['servings'],'source_url':r['source_url'],
                          'source_type':r['source_type'],'ingredient_count':len(json.loads(r['ingredients_json'])),'created_at':r['created_at']} for r in rs]}

    @app.post('/api/v13/recipes')
    def save_recipe(d:RecipeIn,user=Depends(auth)):
        ing,info=parse_recipe(d.ingredients_text)
        link=normalize_url(d.source_url)
        with connect() as db:
            c=db.execute('''INSERT INTO v13_recipes(user_id,name,source_url,source_type,servings,raw_text,ingredients_json,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?)''',(user['id'],d.name.strip(),link,'schema.org JSON pegado' if info['is_schema_org'] else 'texto pegado',d.servings,d.ingredients_text,json.dumps(ing,ensure_ascii=False),now(),now()))
            return {'id':c.lastrowid,'ingredients':ing}

    @app.get('/api/v13/recipes/{rid}')
    def get_recipe(rid:int,user=Depends(auth)):
        with connect() as db:row=own_recipe(db,user['id'],rid)
        return {**{k:row[k] for k in ('id','name','servings','source_url','source_type','raw_text','created_at')},
                'ingredients':json.loads(row['ingredients_json'])}

    @app.delete('/api/v13/recipes/{rid}')
    def delete_recipe(rid:int,user=Depends(auth)):
        with connect() as db:
            own_recipe(db,user['id'],rid)
            db.execute('DELETE FROM v13_recipes WHERE id=?',(rid,))
        return {'ok':True}

    @app.post('/api/v13/recipes/{rid}/compare')
    def compare(rid:int,d:RecipeScale,user=Depends(auth)):
        with connect() as db:
            row=own_recipe(db,user['id'],rid)
            if d.place_id is not None:
                if not one(db,'SELECT id FROM places WHERE user_id=? AND id=?',(user['id'],d.place_id)):
                    raise HTTPException(404,'Lugar no encontrado')
                stores=many(db,'SELECT DISTINCT s.chain FROM place_stores ps JOIN stores s ON s.id=ps.store_id WHERE ps.place_id=?',(d.place_id,))
                chains=sorted({x['chain'] for x in stores}) or sorted({x['chain'] for x in DATA['items']})
            else:chains=sorted({x['chain'] for x in DATA['items']})
        row['requested_servings']=d.servings
        row['mapping']=json.loads(row['overrides_json'])
        return recipe_compare(row,selected_chains=chains)

    @app.put('/api/v13/recipes/{rid}/choice')
    def choose(rid:int,d:Choice,user=Depends(auth)):
        with connect() as db:
            row=own_recipe(db,user['id'],rid)
            ingredients=json.loads(row['ingredients_json'])
            if d.ingredient_index>=len(ingredients):raise HTTPException(400,'Ingrediente fuera de rango')
            if d.listing_id is not None:
                correct={x['listing_id'] for x in candidates(ingredients[d.ingredient_index],d.chain)}
                alternate={x['listing_id'] for x in substitute_candidates(ingredients[d.ingredient_index],d.chain)}
                if d.listing_id in alternate and not d.confirm_alternative:
                    raise HTTPException(400,'Debes confirmar expresamente la sustitución de ingrediente')
                if d.listing_id not in correct|alternate:
                    raise HTTPException(400,'Alternativa no compatible con el ingrediente; selecciona manualmente otro producto en tienda')
            mapping=json.loads(row['overrides_json']);key=f'{d.chain}:{d.ingredient_index}'
            if d.listing_id:mapping[key]=d.listing_id
            else:mapping.pop(key,None)
            db.execute('UPDATE v13_recipes SET overrides_json=?,updated_at=? WHERE id=?',(json.dumps(mapping),now(),rid))
        return {'ok':True}

    @app.post('/api/v13/recipes/{rid}/to-basket')
    def to_basket(rid:int,d:Convert,user=Depends(auth)):
        with connect() as db:
            row=own_recipe(db,user['id'],rid)
            if d.place_id is not None:
                if not one(db,'SELECT id FROM places WHERE id=? AND user_id=?',(d.place_id,user['id'])):raise HTTPException(404,'Lugar no encontrado')
            data={**row,'requested_servings':d.servings,'mapping':json.loads(row['overrides_json'])}
            cmp=recipe_compare(data,selected_chains=[d.chain])['comparisons'][0]
            cursor=db.execute('''INSERT INTO baskets(owner_id,title,kind,place_id,notes,created_at,updated_at,cover_emoji,accent,topics_json)
              VALUES (?,?,?,?,?,?,?,?,?,?)''',(user['id'],'🍽️ '+row['name'][:70],'ocasional',d.place_id,
              f'Receta importada · {d.servings} raciones · {d.chain} · precios web históricos no garantizados',now(),now(),'🍽️','peach','["receta"]'))
            basket_id=cursor.lastrowid
            linked={r['listing_id']:r['product_id'] for r in many(db,'SELECT listing_id,product_id FROM retail_catalog_links')}
            catalog_count=0;free_count=0
            for match in cmp['aggregate_items']:
                if linked.get(match['listing_id']):
                    pid=linked[match['listing_id']]
                    db.execute('INSERT INTO basket_items(basket_id,product_id,quantity) VALUES(?,?,?)',
                               (basket_id,pid,match['packs']))
                    catalog_count+=1
            for obj in cmp['lines']:
                if not obj['match'] or not linked.get(obj['match']['listing_id']):
                    ing=obj['ingredient']
                    db.execute('INSERT INTO basket_free_items(basket_id,title,quantity,created_at) VALUES(?,?,?,?)',
                               (basket_id,ing['raw']+' · por verificar en tienda',1,now()))
                    free_count+=1
            return {'basket_id':basket_id,'matched_lines':catalog_count,'unmatched_lines':free_count,
                    'note':'Cesta editable, sin pedido enviado. Cantidad de productos comerciales = envases completos propuestos; alérgenos y stock por comprobar.'}
