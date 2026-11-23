"""Regression of the previously missing cross-version migration and private backup."""
import os, sqlite3, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_safe_migration_v8_preserves_basket_and_rotates_passwords(tmp_path,monkeypatch):
    import db
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'source_v8.sqlite3')
    monkeypatch.setenv('SHOPPER_DEMO','0')
    db.init()
    source=tmp_path/'source_v8.sqlite3'
    with db.connect() as c:
        salt,digest=db.pbkdf2('old-local-password')
        c.execute('INSERT INTO users(username,display_name,salt,passhash,created_at,friend_code) VALUES (?,?,?,?,?,?)',
                  ('familia','Persona de prueba',salt,digest,db.now(),'f-0001'))
        c.execute('INSERT INTO baskets(owner_id,title,kind,created_at,updated_at) VALUES (?,?,?,?,?)',
                  (1,'Compra familiar','weekly',db.now(),db.now()))
        c.execute("INSERT INTO sessions(token_digest,user_id,created_at,expires_at) VALUES (?,?,?,?)",('old_session',1,db.now(),'2099-01-01'))
        c.execute('DROP TABLE family_tasks')  # reproduce a V8 database
    destination=tmp_path/'private_data'/'shopper.sqlite3'
    runner=ROOT/'tools/migrar_desde_v7_v8.py'
    result=subprocess.run([sys.executable,str(runner),'--origen',str(source),'--destino',str(destination)],
                          cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stderr+result.stdout
    assert source.exists() and destination.exists()
    with sqlite3.connect(source) as c:
        assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==1
        assert c.execute("SELECT title FROM baskets").fetchone()[0]=='Compra familiar'
    with sqlite3.connect(destination) as c:
        assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==0
        assert c.execute("SELECT title FROM baskets").fetchone()[0]=='Compra familiar'
        assert c.execute("SELECT name FROM sqlite_master WHERE name='family_tasks'").fetchone()
        salt,hashed=c.execute("SELECT salt,passhash FROM users WHERE username='familia'").fetchone()
        assert db.pbkdf2('old-local-password',salt)[1]!=hashed
    credentials=(destination.parent/'credenciales_migracion_PRIVADAS.txt').read_text()
    new_pwd=credentials.split('familia: ',1)[1].splitlines()[0]
    assert db.pbkdf2(new_pwd,salt)[1]==hashed
    second=subprocess.run([sys.executable,str(runner),'--origen',str(source),'--destino',str(destination)],
                          cwd=ROOT,capture_output=True,text=True)
    assert second.returncode!=0
    assert 'YA existe' in second.stdout+second.stderr


def test_backup_detects_private_data_path(tmp_path):
    root_copy=tmp_path/'standalone'
    (root_copy/'tools').mkdir(parents=True)
    (root_copy/'data').mkdir()
    script=ROOT/'tools/backup_local.py'
    dbpath=root_copy/'data/shopper.sqlite3'
    with sqlite3.connect(dbpath) as c:c.execute('CREATE TABLE test(value TEXT)');c.execute("INSERT INTO test VALUES ('preserved')")
    # Test default detection through the same code from a temporary app root.
    test_script=root_copy/'tools/backup_local.py'
    test_script.write_bytes(script.read_bytes())
    env={k:v for k,v in os.environ.items() if k!='SHOPPER_DB'}
    run=subprocess.run([sys.executable,str(test_script)],cwd=root_copy,env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr+run.stdout
    backups=list((root_copy/'data/backups').glob('shopper_copia_*.sqlite3'))
    assert len(backups)==1
    with sqlite3.connect(backups[0]) as c:
        assert c.execute('SELECT value FROM test').fetchone()[0]=='preserved'
