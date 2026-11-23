#!/usr/bin/env python3
"""Create a consistent private SQLite backup of SHOPPER, including private iPhone mode.

No server shutdown required: SQLite's online backup API captures a consistent snapshot.
Keep backup files encrypted and never commit them to source control.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def find_database(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env=os.getenv('SHOPPER_DB')
    if env:
        return Path(env).expanduser().resolve()
    # The standard private launcher sets SHOPPER_DB inside its subprocess, not in
    # the user's terminal, so prefer the persisted private data path here.
    for path in (ROOT/'data'/'shopper.sqlite3',ROOT/'shopper_v9.sqlite3',ROOT/'shopper_v7.sqlite3'):
        if path.exists():return path.resolve()
    raise SystemExit('No se encontró una base de datos. Usa --db RUTA para indicarla.')

def main() -> None:
    p=argparse.ArgumentParser(description='Crear copia consistente de SHOPPER para guardarla cifrada')
    p.add_argument('--db',help='Ruta exacta de SQLite (opcional; detecta data/shopper.sqlite3)')
    p.add_argument('--dir',help='Directorio destino (por defecto backups/ junto a la base)')
    a=p.parse_args()
    source_path=find_database(a.db)
    if not source_path.is_file():raise SystemExit('La base de datos indicada no existe: '+str(source_path))
    dest_dir=Path(a.dir).expanduser().resolve() if a.dir else source_path.parent/'backups'
    dest_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    dest=dest_dir/f'shopper_copia_{stamp}.sqlite3'
    with sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True) as source:
        with sqlite3.connect(dest) as out:
            source.backup(out)
            status=out.execute('PRAGMA quick_check').fetchone()[0]
            if status!='ok':raise RuntimeError('Copia inválida: '+status)
    try:os.chmod(dest,0o600)
    except OSError:pass
    print('Copia creada:',dest)
    print('Contiene datos personales. Consérvala protegida y fuera de repositorios compartidos.')

if __name__=='__main__':main()
