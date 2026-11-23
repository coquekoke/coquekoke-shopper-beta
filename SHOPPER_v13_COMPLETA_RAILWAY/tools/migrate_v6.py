#!/usr/bin/env python3
"""One-time, explicit V6 demo-data import into an *existing* V7 local DB.

Source is opened read-only. Only records owned by V6 demo profiles (IDs 1/2)
can be mapped to V7 demo accounts. New private V7 accounts cannot be inferred
from a V6 profile selector. This is *not* a production migration.
"""
from __future__ import annotations
import argparse, hashlib, sqlite3, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db import connect, init, now


def main():
    parser=argparse.ArgumentParser(description='Importar datos de demostración v6 a SHOPPER v7 local')
    parser.add_argument('v6_database',help='Ruta a shopper_local.sqlite3 de la versión 6')
    parser.add_argument('--confirm',action='store_true',help='Ejecutar importación real; sin esto solo muestra instrucciones')
    args=parser.parse_args()
    p=Path(args.v6_database).expanduser().resolve()
    if not p.is_file():parser.error('No existe el archivo v6 indicado')
    if not args.confirm:
        print('Importación local sin tocar el original. Haz antes una copia de seguridad de la BD v7.')
        print(f'Para continuar: python tools/migrate_v6.py "{p}" --confirm')
        return
    init()
    source=sqlite3.connect('file:'+p.as_posix()+'?mode=ro',uri=True)
    source.row_factory=sqlite3.Row
    source.execute('PRAGMA query_only=ON')
    def rows(table):
        try:return [dict(r) for r in source.execute(f'SELECT * FROM {table}')]
        except sqlite3.OperationalError:return []
    uids={1:'maria_demo',2:'lucas_demo'}
    with connect() as dst:
        dst.execute('CREATE TABLE IF NOT EXISTS migration_history (source_sha256 TEXT PRIMARY KEY, created_at TEXT NOT NULL, note TEXT NOT NULL)')
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if dst.execute('SELECT 1 FROM migration_history WHERE source_sha256=?',(digest,)).fetchone():
            print('Este archivo v6 ya fue importado; sin cambios');return
        usermap={}
        for uid,login in uids.items():
            r=dst.execute('SELECT id FROM users WHERE username=?',(login,)).fetchone()
            if r:usermap[uid]=r['id']
        if not usermap:
            raise SystemExit('No hay perfiles demo en la BD v7. Debes usar v7 en modo demostración.')
        storemap={}
        for s in rows('stores'):
            cur=dst.execute('SELECT id FROM stores WHERE name=? AND chain=? ORDER BY id LIMIT 1',(s['name'],s['chain'])).fetchone()
            if not cur:
                cur=dst.execute('INSERT OR IGNORE INTO stores(name,chain,address,municipality,source_type,source_url,verified_at) VALUES (?,?,?,?,?,?,NULL)',
                    (s['name'],s['chain'],s['address'],'Madrid','migrado_v6_no_verificado',s.get('source_url')))
                new_id=cur.lastrowid if cur.rowcount else dst.execute('SELECT id FROM stores WHERE name=? AND address=?',(s['name'],s['address'])).fetchone()['id']
            else:new_id=cur['id']
            storemap[s['id']]=new_id
        brandmap={}
        for b in rows('brands'):
            grp=(b.get('corporate_group') or 'Grupo no identificado').removeprefix('Grupo ').strip()
            group=dst.execute('SELECT id FROM groups WHERE lower(name)=lower(?)',(grp,)).fetchone()
            if group:gid=group['id']
            else:gid=dst.execute('INSERT INTO groups(name,sector,evidence_url,evidence_note) VALUES(?,?,?,?)',
                 (grp,'Alimentación',b.get('evidence_url'),'Migrado de v6, no auditado')).lastrowid
            x=dst.execute('SELECT id FROM brands WHERE name=?',(b['name'],)).fetchone()
            if x:brandmap[b['id']]=x['id']
            else:brandmap[b['id']]=dst.execute('INSERT INTO brands(name,group_id,evidence_url,relationship) VALUES(?,?,?,?)',
                (b['name'],gid,b.get('evidence_url'),b.get('relation') or 'relación por verificar')).lastrowid
        productmap={}
        for pr in rows('products'):
            found=dst.execute('SELECT id FROM products WHERE gtin=?',(pr['gtin'],)).fetchone() if pr.get('gtin') else None
            if not found:found=dst.execute('SELECT id FROM products WHERE name=?',(pr['name'],)).fetchone()
            if found:productmap[pr['id']]=found['id']
            else:
                productmap[pr['id']]=dst.execute('''INSERT INTO products(name,gtin,brand_id,category,format_text,ingredients,nutrition_note,
                   origin_note,source_url,source_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                   (pr['name'],pr.get('gtin'),brandmap.get(pr.get('brand_id')),pr.get('category') or 'General','',
                    pr.get('ingredients'),pr.get('nutriments'),pr.get('origin_text'),pr.get('origin_source'),
                    'Importado de v6; ventas, origen y precios NO verificados',now())).lastrowid
        placemap={}
        for pl in rows('places'):
            uid=usermap.get(pl['owner_id'])
            if not uid:continue
            x=dst.execute('SELECT id FROM places WHERE user_id=? AND name=?',(uid,pl['name'])).fetchone()
            placemap[pl['id']]=x['id'] if x else dst.execute('INSERT INTO places(user_id,name,address,created_at) VALUES(?,?,?,?)',
                (uid,pl['name'],pl.get('address'),now())).lastrowid
        for n in rows('place_store_network'):
            pid=placemap.get(n['place_id']);sid=storemap.get(n['store_id'])
            if pid and sid:dst.execute('INSERT OR IGNORE INTO place_stores(place_id,store_id) VALUES(?,?)',(pid,sid))
        basketmap={}
        for b in rows('baskets'):
            uid=usermap.get(b['owner_id'])
            if not uid:continue
            if b['kind']=='actual':
                x=dst.execute('SELECT id FROM baskets WHERE owner_id=? AND kind=?',(uid,'actual')).fetchone()
                if x:basketmap[b['id']]=x['id'];continue
            basketmap[b['id']]=dst.execute('''INSERT INTO baskets(owner_id,title,kind,place_id,event_on,notes,created_at,updated_at)
                 VALUES(?,?,?,?,?,?,?,?)''',(uid,b['title'],b['kind'] if b['kind'] in ('evento','semanal','mensual','ocasional') else 'ocasional',
                 placemap.get(b.get('place_id')),b.get('event_date'),b.get('notes') or '',now(),now())).lastrowid
        for it in rows('basket_items'):
            bid=basketmap.get(it['basket_id']);pid=productmap.get(it['product_id'])
            if bid and pid:dst.execute('INSERT INTO basket_items(basket_id,product_id,quantity) VALUES(?,?,?) ON CONFLICT(basket_id,product_id) DO NOTHING',
                (bid,pid,it['quantity']))
        for m in rows('basket_members'):
            bid=basketmap.get(m['basket_id']);uid=usermap.get(m['user_id'])
            if bid and uid and m.get('role') in ('editor','reader'):
                dst.execute('INSERT OR IGNORE INTO basket_members(basket_id,user_id,role,created_at) VALUES(?,?,?,?)',(bid,uid,m['role'],now()))
        for pa in rows('pantry_items'):
            uid=usermap.get(pa['user_id'])
            if not uid:continue
            state=pa.get('state','active')
            dst.execute('''INSERT INTO pantry(user_id,custom_name,quantity,unit,expires_on,estimated_value_cents,state,created_at,closed_at)
            VALUES (?,?,?,?,?,?,?,?,?)''',(uid,pa['product_name'],pa['quantity'],pa['unit'],pa.get('expires_on'),
               pa.get('estimated_value_cents'),state if state in ('active','used','discarded') else 'active',now(),pa.get('closed_at')))
        for ob in rows('price_observations'):
            uid=usermap.get(ob['user_id']);sid=storemap.get(ob['store_id']);pid=productmap.get(ob['product_id'])
            if uid and sid and pid:
                dst.execute('''INSERT INTO price_observations(product_id,store_id,user_id,amount_cents,source_type,note,observed_at)
                 VALUES(?,?,?,?,?,?,?)''',(pid,sid,uid,ob['price_cents'],ob.get('source') or 'migrado',ob.get('note') or 'Migrado de v6',ob.get('observed_at') or now()))
        for rv in rows('reviews'):
            uid=usermap.get(rv['user_id']);pid=productmap.get(rv['product_id'])
            if uid and pid:dst.execute('''INSERT INTO reviews(user_id,product_id,quality,value,comment,updated_at) VALUES(?,?,?,?,?,?)
               ON CONFLICT(user_id,product_id) DO NOTHING''',(uid,pid,rv['quality'],rv['value'],rv.get('note') or '',now()))
        for rr in rows('reports'):
            uid=usermap.get(rr['user_id']);sid=storemap.get(rr['store_id']);pid=productmap.get(rr['product_id'])
            if uid and sid and pid:
                dst.execute('''INSERT INTO live_reports(reporter_id,store_id,product_id,kind,price_cents,note,observed_at,expires_at,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)''',(uid,sid,pid,rr['kind'],rr.get('price_cents'),rr.get('note') or '',rr['observed_at'],rr['expires_at'],now()))
        for a in rows('shopper_applications'):
            uid=usermap.get(a['user_id'])
            if uid:
                dst.execute('''INSERT INTO shopper_profiles(user_id,status,updated_at) VALUES (?,?,?) ON CONFLICT(user_id)
                  DO NOTHING''',(uid,'draft',now()))
        dst.execute('INSERT INTO migration_history(source_sha256,created_at,note) VALUES(?,?,?)',
                    (digest,now(),'V6 demo; no importa borradores, claves ni autorizaciones de trabajo'))
        print('Importación finalizada:',{'tiendas':len(storemap),'productos':len(productmap),'lugares':len(placemap),'cestas':len(basketmap)})
        print('NO se migran autorizaciones, sesiones ni pedidos: se mantienen en modo borrador o histórico v6.')
    source.close()

if __name__=='__main__': main()
