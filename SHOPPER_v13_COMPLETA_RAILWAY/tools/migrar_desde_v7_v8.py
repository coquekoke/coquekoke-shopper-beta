#!/usr/bin/env python3
"""Offline, fail-closed transfer of a SHOPPER 7/8 SQLite database into private SHOPPER 9.

Source remains unchanged. Every existing password is rotated and old sessions are
revoked: credentials for the migrated private instance are written to a private
local file, one temporary password per person. Do not send the file to a group.
"""
from __future__ import annotations
import argparse, os, secrets, sqlite3, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import db as shopper_db

NECESSARY={'users','baskets','basket_items','basket_members','pantry','products','stores','sessions'}

def migrate(src:Path,dest:Path) -> tuple[Path,int]:
    src=src.expanduser().resolve();dest=dest.expanduser().resolve()
    if not src.is_file():raise ValueError('No existe el archivo de origen: '+str(src))
    if src==dest:raise ValueError('El origen y destino no pueden ser iguales')
    if dest.exists():raise ValueError('El destino YA existe; no se sobrescribirá ningún dato: '+str(dest))
    dest.parent.mkdir(parents=True,exist_ok=True)
    secrets_file=dest.parent/'credenciales_migracion_PRIVADAS.txt'
    if secrets_file.exists():raise ValueError('Ya existe un archivo de credenciales de migración: protégelo antes de intentarlo otra vez')
    fd,tmp_filename=tempfile.mkstemp(prefix='.shopper_migracion_',suffix='.sqlite3',dir=str(dest.parent))
    os.close(fd)
    temp=Path(tmp_filename)
    secrets_tmp=None
    try:
        with sqlite3.connect(src.as_uri()+'?mode=ro',uri=True) as original:
            tables={r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not NECESSARY.issubset(tables):
                raise ValueError('El origen no parece una base SHOPPER 7/8 válida. Faltan tablas: '+', '.join(sorted(NECESSARY-tables)))
            if original.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise ValueError('La base de origen no supera la comprobación de integridad')
            with sqlite3.connect(temp) as copy:
                original.backup(copy)
        shopper_db.DB_PATH=temp
        shopper_db.init()  # conservative additive schema changes (including family_tasks)
        temporary_credentials=[]
        with shopper_db.connect() as copy:
            accounts=copy.execute('SELECT id, username FROM users ORDER BY id').fetchall()
            copy.execute('DELETE FROM sessions')
            for account in accounts:
                password=secrets.token_urlsafe(24)
                salt,digest=shopper_db.pbkdf2(password)
                copy.execute('UPDATE users SET salt=?,passhash=? WHERE id=?',(salt,digest,account['id']))
                temporary_credentials.append(f'{account["username"]}: {password}')
        with sqlite3.connect(temp) as copy:
            copy.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            if copy.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise ValueError('La copia migrada no supera la comprobación de integridad')
            if copy.execute('SELECT COUNT(*) FROM users').fetchone()[0]!=len(temporary_credentials):
                raise ValueError('La cantidad de cuentas no coincide tras la migración')
        content=('SHOPPER — CONTRASEÑAS TEMPORALES PRIVADAS\n'
                 'El origen NO se ha modificado. Las sesiones anteriores han sido cerradas.\n'
                 'Cada persona debe acceder con su contraseña provisional y cambiarla al entrar.\n'
                 'ENTREGA INDIVIDUALMENTE solo la contraseña de cada destinatario.\n'
                 'Borra este archivo cuando todas las personas hayan cambiado su contraseña.\n\n'
                 + '\n'.join(temporary_credentials) + '\n')
        fd, temp_cred=tempfile.mkstemp(prefix='.credenciales_migracion_',suffix='.txt',dir=str(dest.parent))
        secrets_tmp=Path(temp_cred)
        with os.fdopen(fd,'w',encoding='utf-8') as out:out.write(content)
        try:os.chmod(secrets_tmp,0o600);os.chmod(temp,0o600)
        except OSError:pass
        os.replace(secrets_tmp,secrets_file)
        secrets_tmp=None
        os.replace(temp,dest)
        return secrets_file,len(temporary_credentials)
    finally:
        temp.unlink(missing_ok=True)
        if secrets_tmp:secrets_tmp.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description='Migrar datos de SHOPPER 7/8 a SHOPPER privado; cierra ambos servidores antes de usar')
    p.add_argument('--origen',required=True,help='Ruta del archivo .sqlite3 antiguo')
    p.add_argument('--destino',default=str(ROOT/'data'/'shopper.sqlite3'),help='Base nueva; debe NO existir')
    a=p.parse_args()
    try:creds,n=migrate(Path(a.origen),Path(a.destino))
    except (ValueError,sqlite3.Error,OSError) as exc:sys.exit('MIGRACIÓN NO REALIZADA: '+str(exc))
    print('Migración completada; origen intacto. Usuarios:',n)
    print('Credenciales privadas generadas en:',creds)
    print('Protege ese archivo; entrega contraseñas individuales y exige cambiarlas.')
    print('Arranca SHOPPER privado una vez revisados los datos. NO publiques el archivo de credenciales.')

if __name__=='__main__':main()
