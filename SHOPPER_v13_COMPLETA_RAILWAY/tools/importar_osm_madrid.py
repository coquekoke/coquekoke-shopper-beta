#!/usr/bin/env python3
"""Importa al directorio SHOPPER un fichero JSON obtenido lícitamente de OpenStreetMap/Overpass.

Uso: SHOPPER_DB=/ruta/a/base.sqlite3 python tools/importar_osm_madrid.py madrid_supermercados.json
Consulta ejemplo: docs/overpass_madrid.txt. El fichero JSON puede ser un extracto de Overpass.
IMPORTANTE: conservar atribución ODbL y no usar endpoint publico para sincronización masiva continua.
"""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from db import connect, init
from v12api import migrate, import_overpass

def import_file(path,cap=200_000):
    data=json.loads(Path(path).read_text('utf-8'))
    items=data.get('elements') if isinstance(data,dict) else data
    if not isinstance(items,list):raise ValueError('Se requiere una lista de elementos OSM / Overpass JSON')
    init(); migrate()
    total={'added':0,'updated':0}
    for off in range(0,len(items),600):
        with connect() as db: r=import_overpass(db,items[off:off+600],cap=600)
        for k in total:total[k]+=r[k]
    return {**total,'source':'OpenStreetMap contributors · ODbL','elements_read':len(items)}

if __name__=='__main__':
    if len(sys.argv)!=2:
        print('Uso: python tools/importar_osm_madrid.py ruta_a_exportacion_overpass.json');sys.exit(2)
    print(json.dumps(import_file(sys.argv[1]),ensure_ascii=False,indent=2))
