"""Import a user-provided Overpass JSON export into SHOPPER's local store directory.

Use only under OpenStreetMap ODbL and attribution terms. Never claims exhaustive or verified shops.
No network calls. Default dry-run. Run with --apply to make local changes.
"""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db import connect, one, init

def clean(value,maxlen=200):return str(value or '').strip()[:maxlen]

def convert(element):
    tags=element.get('tags') or {}
    shop=tags.get('shop')
    if shop not in ('supermarket','convenience','grocery','department_store'):
        return None
    coords=element if element.get('type')=='node' else element.get('center',{})
    lat,lon=coords.get('lat'),coords.get('lon')
    if lat is None or lon is None:return None
    name=clean(tags.get('name') or tags.get('brand') or tags.get('operator') or 'Supermercado sin nombre',100)
    chain=clean(tags.get('brand') or tags.get('operator') or name,80)
    street=' '.join(filter(None,[clean(tags.get('addr:street'),120),clean(tags.get('addr:housenumber'),15)])).strip()
    locality=clean(tags.get('addr:city') or tags.get('addr:municipality') or tags.get('addr:suburb'),80)
    postcode=clean(tags.get('addr:postcode'),20)
    # An absent address stays explicit; coordinates still allow locating the element.
    parts=[x for x in (street,postcode,locality) if x]
    addr=', '.join(parts)+(', Comunidad de Madrid, España' if parts else 'Dirección postal no registrada · Comunidad de Madrid, España')
    typ=element.get('type');ref=element.get('id')
    if typ not in ('node','way','relation') or not isinstance(ref,int):return None
    return {'name':name,'chain':chain,'address':addr,'municipality':locality,'lat':lat,'lon':lon,
            'source_type':'OpenStreetMap (ODbL; colaborativo, NO verificado)',
            'source_url':f'https://www.openstreetmap.org/{typ}/{ref}'}

def run():
    parser=argparse.ArgumentParser(description='Importador OSM de tiendas para piloto LOCAL; exige ODbL + atribución.')
    parser.add_argument('json_file',type=Path,help='Resultado JSON exportado de Overpass (elements)')
    parser.add_argument('--apply',action='store_true',help='Importa. Sin este argumento solo previsualiza el número de registros.')
    parser.add_argument('--limit',type=int,default=3000)
    args=parser.parse_args()
    data=json.loads(args.json_file.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or not isinstance(data.get('elements'),list):
        raise SystemExit('JSON inválido: falta lista elements de Overpass')
    if len(data['elements'])>20000:raise SystemExit('Archivo demasiado grande para esta herramienta de piloto')
    records=[r for e in data['elements'] if (r:=convert(e))]
    if len(records)>args.limit:records=records[:args.limit]
    print(f'Registros georreferenciados y tipificados: {len(records)}; ejecutar --apply para guardar.')
    if not args.apply:return
    init()
    inserted=0;skipped=0
    with connect() as db:
        for r in records:
            if one(db,'SELECT id FROM stores WHERE source_url=?',(r['source_url'],)) or one(db,'SELECT id FROM stores WHERE lower(name)=lower(?) AND lower(address)=lower(?)',(r['name'],r['address'])):
                skipped+=1;continue
            db.execute('''INSERT INTO stores(name,chain,address,municipality,region,lat,lon,source_type,source_url,verified_at)
               VALUES (?,?,?,?,'Madrid',?,?,?,?,NULL)''',
               (r['name'],r['chain'],r['address'],r['municipality'],r['lat'],r['lon'],r['source_type'],r['source_url']))
            inserted+=1
    print(f'Insertados: {inserted}; duplicados exactos descartados: {skipped}. Revisar direcciones y aperturas.')

if __name__=='__main__':run()
