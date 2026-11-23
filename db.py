"""SQLite store for SHOPPER 9.1 private-family single-instance beta.
For trusted HTTPS via Tailscale; further security review for public availability.
"""
from __future__ import annotations
import hashlib, os, secrets, sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB_PATH=Path(os.getenv('SHOPPER_DB',str(ROOT/'shopper_v9.sqlite3')))

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def pbkdf2(password: str, salt: str | None=None):
    salt=salt or secrets.token_hex(16)
    value=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),260_000).hex()
    return salt,value

def token_hash(token: str):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(DB_PATH),timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def many(db,sql,args=()):
    return [dict(row) for row in db.execute(sql,args)]

def one(db,sql,args=()):
    row=db.execute(sql,args).fetchone()
    return dict(row) if row else None

SCHEMA='''
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT NOT NULL UNIQUE,
 display_name TEXT NOT NULL,salt TEXT NOT NULL,passhash TEXT NOT NULL,
 created_at TEXT NOT NULL, friend_code TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 token_digest TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS groups(
 id INTEGER PRIMARY KEY,name TEXT NOT NULL,parent_id INTEGER REFERENCES groups(id),
 sector TEXT NOT NULL DEFAULT 'Alimentación', evidence_url TEXT, evidence_note TEXT);
CREATE TABLE IF NOT EXISTS brands(
 id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE, group_id INTEGER REFERENCES groups(id),
 evidence_url TEXT, relationship TEXT NOT NULL DEFAULT 'marca del grupo');
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL, gtin TEXT UNIQUE,brand_id INTEGER REFERENCES brands(id),
 category TEXT NOT NULL, format_text TEXT NOT NULL DEFAULT '', ingredients TEXT, allergens TEXT,
 nutrition_note TEXT, origin_note TEXT, source_url TEXT, source_status TEXT NOT NULL,
 added_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_products_category ON products(category);
CREATE TABLE IF NOT EXISTS stores(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL, chain TEXT NOT NULL,
 address TEXT NOT NULL,municipality TEXT NOT NULL DEFAULT '', region TEXT NOT NULL DEFAULT 'Madrid',
 lat REAL,lon REAL,source_type TEXT NOT NULL,source_url TEXT,verified_at TEXT,
 added_by INTEGER REFERENCES users(id),prep_integrated INTEGER NOT NULL DEFAULT 0,
 UNIQUE(name,address));
CREATE TABLE IF NOT EXISTS places(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, address TEXT,lat REAL,lon REAL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS place_stores(
 place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
 store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,PRIMARY KEY(place_id,store_id));
CREATE TABLE IF NOT EXISTS friendships(
 u_low INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 u_high INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL,PRIMARY KEY(u_low,u_high),CHECK(u_low<u_high));
CREATE TABLE IF NOT EXISTS baskets(
 id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL,kind TEXT NOT NULL,place_id INTEGER REFERENCES places(id) ON DELETE SET NULL,
 event_on TEXT,budget_cents INTEGER,notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS basket_members(
 basket_id INTEGER NOT NULL REFERENCES baskets(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('editor','reader')),
 created_at TEXT NOT NULL,PRIMARY KEY(basket_id,user_id));
CREATE TABLE IF NOT EXISTS basket_items(
 basket_id INTEGER NOT NULL REFERENCES baskets(id) ON DELETE CASCADE,
 product_id INTEGER NOT NULL REFERENCES products(id),quantity REAL NOT NULL CHECK(quantity>0),
 checked INTEGER NOT NULL DEFAULT 0,checked_by INTEGER REFERENCES users(id),checked_at TEXT,
 PRIMARY KEY(basket_id,product_id));
CREATE TABLE IF NOT EXISTS basket_free_items(
 id INTEGER PRIMARY KEY AUTOINCREMENT,basket_id INTEGER NOT NULL REFERENCES baskets(id) ON DELETE CASCADE,
 title TEXT NOT NULL,quantity REAL NOT NULL CHECK(quantity>0), checked INTEGER NOT NULL DEFAULT 0,
 checked_by INTEGER REFERENCES users(id),checked_at TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invite_codes(
 code_digest TEXT PRIMARY KEY,kind TEXT NOT NULL,resource_id INTEGER NOT NULL,
 created_by INTEGER NOT NULL REFERENCES users(id),role TEXT,
 expires_at TEXT NOT NULL,claimed_by INTEGER REFERENCES users(id), claimed_at TEXT);
CREATE TABLE IF NOT EXISTS pantry(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),
 product_id INTEGER REFERENCES products(id),custom_name TEXT,quantity REAL NOT NULL, unit TEXT NOT NULL,
 expires_on TEXT,estimated_value_cents INTEGER,state TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL,closed_at TEXT,
 CHECK(product_id IS NOT NULL OR custom_name IS NOT NULL));
CREATE TABLE IF NOT EXISTS price_observations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL REFERENCES products(id),
 store_id INTEGER NOT NULL REFERENCES stores(id),user_id INTEGER NOT NULL REFERENCES users(id),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),source_type TEXT NOT NULL,
 note TEXT NOT NULL DEFAULT '',observed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_price_lookup ON price_observations(product_id,store_id,observed_at DESC);
CREATE TABLE IF NOT EXISTS live_reports(
 id INTEGER PRIMARY KEY AUTOINCREMENT,reporter_id INTEGER NOT NULL REFERENCES users(id),
 store_id INTEGER NOT NULL REFERENCES stores(id),product_id INTEGER NOT NULL REFERENCES products(id),
 kind TEXT NOT NULL, price_cents INTEGER,note TEXT NOT NULL DEFAULT '',
 observed_at TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open');
CREATE TABLE IF NOT EXISTS live_confirmations(
 report_id INTEGER NOT NULL REFERENCES live_reports(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
 PRIMARY KEY(report_id,user_id));
CREATE TABLE IF NOT EXISTS live_flags(
 report_id INTEGER NOT NULL REFERENCES live_reports(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id), reason TEXT NOT NULL,
 created_at TEXT NOT NULL,PRIMARY KEY(report_id,user_id));
CREATE TABLE IF NOT EXISTS reviews(
 user_id INTEGER NOT NULL REFERENCES users(id),product_id INTEGER NOT NULL REFERENCES products(id),
 quality INTEGER NOT NULL CHECK(quality BETWEEN 1 AND 5),value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 5),
 comment TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,product_id));
CREATE TABLE IF NOT EXISTS shopper_profiles(
 user_id INTEGER PRIMARY KEY REFERENCES users(id),status TEXT NOT NULL DEFAULT 'not_applied',
 travel_mode TEXT NOT NULL DEFAULT 'walking',min_notice_hours INTEGER NOT NULL DEFAULT 6,
 min_window_mins INTEGER NOT NULL DEFAULT 60,max_distance_km INTEGER NOT NULL DEFAULT 5,
 availability_note TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_drafts(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),
 basket_id INTEGER NOT NULL REFERENCES baskets(id),store_id INTEGER REFERENCES stores(id),
 place_id INTEGER REFERENCES places(id),mode TEXT NOT NULL,window_start TEXT NOT NULL,
 window_mins INTEGER NOT NULL,notice_hours INTEGER NOT NULL,recipient_alias TEXT NOT NULL DEFAULT '',
 shopping_snapshot TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'DRAFT_NOT_SENT',created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS store_sightings(
 id INTEGER PRIMARY KEY AUTOINCREMENT, store_id INTEGER NOT NULL REFERENCES stores(id),
 product_id INTEGER NOT NULL REFERENCES products(id),user_id INTEGER NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL CHECK(kind IN ('seen','not_found')),
 note TEXT NOT NULL DEFAULT '',observed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_sightings_lookup ON store_sightings(store_id,product_id,observed_at DESC);
CREATE TABLE IF NOT EXISTS price_watches(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 product_id INTEGER NOT NULL REFERENCES products(id),store_id INTEGER REFERENCES stores(id),
 threshold_cents INTEGER,created_at TEXT NOT NULL,price_after_id INTEGER NOT NULL DEFAULT 0,report_after_id INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS ix_watches_unique ON price_watches(user_id,product_id,COALESCE(store_id,0));
CREATE TABLE IF NOT EXISTS pantry_movements(
 id INTEGER PRIMARY KEY AUTOINCREMENT,pantry_id INTEGER NOT NULL REFERENCES pantry(id),
 user_id INTEGER NOT NULL REFERENCES users(id),quantity REAL NOT NULL CHECK(quantity>0),
 kind TEXT NOT NULL CHECK(kind IN ('used','discarded')),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shopping_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),
 basket_id INTEGER REFERENCES baskets(id) ON DELETE SET NULL,store_id INTEGER REFERENCES stores(id),
 basket_name TEXT NOT NULL,store_name TEXT,
 paid_cents INTEGER NOT NULL CHECK(paid_cents>=0),minutes_spent INTEGER,
 notes TEXT NOT NULL DEFAULT '',item_snapshot TEXT NOT NULL,
 recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_runs_user ON shopping_runs(user_id,recorded_at DESC);
CREATE TABLE IF NOT EXISTS family_tasks(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 basket_id INTEGER NOT NULL REFERENCES baskets(id) ON DELETE CASCADE,
 created_by INTEGER NOT NULL REFERENCES users(id),
 assigned_to INTEGER REFERENCES users(id),
 title TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',due_on TEXT,
 store_id INTEGER REFERENCES stores(id),
 status TEXT NOT NULL CHECK(status IN ('open','accepted','done','cancelled')) DEFAULT 'open',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_family_tasks_basket ON family_tasks(basket_id,created_at);
CREATE TABLE IF NOT EXISTS feedback(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),
 area TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
'''

def init():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(SCHEMA)
        if 'checked' not in [r['name'] for r in db.execute('PRAGMA table_info(basket_items)')]:
            db.execute('ALTER TABLE basket_items ADD COLUMN checked INTEGER NOT NULL DEFAULT 0')
        if 'checked_by' not in [r['name'] for r in db.execute('PRAGMA table_info(basket_items)')]:
            db.execute('ALTER TABLE basket_items ADD COLUMN checked_by INTEGER REFERENCES users(id)')
        if 'checked_at' not in [r['name'] for r in db.execute('PRAGMA table_info(basket_items)')]:
            db.execute('ALTER TABLE basket_items ADD COLUMN checked_at TEXT')
        if 'price_after_id' not in [r['name'] for r in db.execute('PRAGMA table_info(price_watches)')]:
            db.execute('ALTER TABLE price_watches ADD COLUMN price_after_id INTEGER NOT NULL DEFAULT 0')
        if 'report_after_id' not in [r['name'] for r in db.execute('PRAGMA table_info(price_watches)')]:
            db.execute('ALTER TABLE price_watches ADD COLUMN report_after_id INTEGER NOT NULL DEFAULT 0')
        if 'created_at' not in [r['name'] for r in db.execute('PRAGMA table_info(live_reports)')]:
            db.execute("ALTER TABLE live_reports ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
            db.execute("UPDATE live_reports SET created_at=observed_at WHERE created_at=''")
        if not one(db,'SELECT id FROM groups LIMIT 1'):
            db.executemany('INSERT INTO groups(id,name,sector,evidence_url,evidence_note) VALUES (?,?,?,?,?)',[
                (1,'Ferrero','Alimentación','https://www.ferrero.com/es/es','Relación corporativa de referencia, no fábrica del lote'),
                (2,'Nestlé','Alimentación','https://empresa.nestle.es/es/marcas','Relación corporativa de referencia, no fábrica del lote')])
            db.executemany('INSERT INTO brands(id,name,group_id,evidence_url) VALUES (?,?,?,?)',[
                (1,'Nutella',1,'https://www.nutella.com/es/es/'),
                (2,'Nescafé',2,'https://empresa.nestle.es/es/marcas/cafe/nescafe')])
            db.executemany('''INSERT INTO products(id,name,gtin,brand_id,category,format_text,source_status,created_at) VALUES (?,?,?,?,?,?,?,?)''',[
                (1,'Nutella 400 g','3017620422003',1,'Despensa','400 g','Referencia identificativa; stock y precios NO verificados',now()),
                (2,'Café soluble Nescafé (genérico)',None,2,'Café','', 'Categoría genérica: no SKU',now()),
                (3,'Manzanas (categoría genérica)',None,None,'Fruta','kg','Categoría genérica: no SKU',now())])
            db.executemany('''INSERT INTO stores(id,name,chain,address,municipality,source_type,source_url,verified_at) VALUES(?,?,?,?,?,?,?,?)''',[
                (1,'DIA · Santo Domingo','DIA','Av. del Guadalix 35–37, C.C. Santo Domingo, Algete, Madrid, España','Algete','directorio comercial','https://www.dia.es/tiendas/buscador-tiendas/madrid/algete',None),
                (2,'Sánchez Romero · Moraleja Green','Sánchez Romero','Av. de Europa 13–15, C.C. Moraleja Green, Alcobendas, Madrid, España','Alcobendas','directorio comercial','https://sanchez-romero.com/tiendas/moraleja/',None)])
        if os.getenv('SHOPPER_DEMO','0') == '1' and not one(db,'SELECT id FROM users LIMIT 1'):
            salt,value=pbkdf2('ShopperDemo2026!')
            db.execute('INSERT INTO users(username,display_name,salt,passhash,created_at,friend_code) VALUES (?,?,?,?,?,?)',
                       ('maria_demo','María (demo)',salt,value,now(),'MARIA-'+secrets.token_hex(4).upper()))
            salt,value=pbkdf2('ShopperDemo2026!')
            db.execute('INSERT INTO users(username,display_name,salt,passhash,created_at,friend_code) VALUES (?,?,?,?,?,?)',
                       ('lucas_demo','Lucas (demo)',salt,value,now(),'LUCAS-'+secrets.token_hex(4).upper()))
            for uid in (1,2):
                db.execute('INSERT INTO baskets(owner_id,title,kind,created_at,updated_at) VALUES (?,?,?,?,?)',
                           (uid,'Actual','actual',now(),now()))
            db.execute('INSERT INTO places(user_id,name,address,created_at) VALUES (?,?,?,?)',
                       (1,'Casa · zona norte','Dirección no configurada',now()))
