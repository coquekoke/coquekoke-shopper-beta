"""Regression: v8 upgrades old-style local schemas without resetting people and cestas."""
import importlib
import sqlite3


def test_existing_v7_style_db_migrates_without_reset(tmp_path,monkeypatch):
    dst=tmp_path/'existing.sqlite3'
    with sqlite3.connect(dst) as con:
        con.executescript('''
        CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,salt TEXT NOT NULL,passhash TEXT NOT NULL,
          created_at TEXT NOT NULL,friend_code TEXT UNIQUE NOT NULL);
        CREATE TABLE baskets(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER NOT NULL,
          title TEXT NOT NULL,kind TEXT NOT NULL,place_id INTEGER,event_on TEXT,
          budget_cents INTEGER,notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE basket_items(basket_id INTEGER NOT NULL,product_id INTEGER NOT NULL,
          quantity REAL NOT NULL,PRIMARY KEY(basket_id,product_id));
        CREATE TABLE live_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,
          reporter_id INTEGER,store_id INTEGER,product_id INTEGER,kind TEXT,
          price_cents INTEGER,note TEXT,observed_at TEXT,expires_at TEXT,status TEXT);
        INSERT INTO users(username,display_name,salt,passhash,created_at,friend_code)
          VALUES ('legacy_user','Prueba legado','aaa','bbb','2026-01-01','FRIEND-1');
        INSERT INTO baskets(owner_id,title,kind,created_at,updated_at)
          VALUES (1,'Cesta heredada','actual','2026-01-01','2026-01-01');
        ''')
    monkeypatch.setenv('SHOPPER_DB',str(dst))
    monkeypatch.setenv('SHOPPER_DEMO','0')
    import db
    importlib.reload(db)
    db.init()
    with db.connect() as con:
        assert con.execute('SELECT username FROM users').fetchone()[0]=='legacy_user'
        assert con.execute('SELECT title FROM baskets').fetchone()[0]=='Cesta heredada'
        assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('shopping_runs','store_sightings','pantry_movements','price_watches')").fetchone()[0]==4
        assert {'checked','checked_by','checked_at'} <= {r['name'] for r in con.execute('PRAGMA table_info(basket_items)')}
        assert 'created_at' in [r['name'] for r in con.execute('PRAGMA table_info(live_reports)')]
        assert 'price_after_id' in [r['name'] for r in con.execute('PRAGMA table_info(price_watches)')]
