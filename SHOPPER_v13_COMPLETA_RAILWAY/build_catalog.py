import json
from pathlib import Path
DAY='2026-11-23'
DIA_RICE='https://www.dia.es/arroz-pastas-y-legumbres/arroz/c/L2042'
DIA_MILK='https://www.dia.es/huevos-leche-y-mantequilla/leche/c/L2051'
CARF='https://www.carrefour.es/supermercado/la-despensa-carrefour/F-13ji8Z10si/c'
items=[]
def add(chain,cat,name,brand,fmt,price,url,sku=None):
    idx=sum(1 for a in items if a['chain']==chain)+1
    items.append(dict(id=f"{chain.lower().replace(' ','-')}-{sku or str(idx).zfill(3)}",chain=chain,category=cat,name=name,brand=brand,format=fmt,price_cents=int(round(price*100)),source_url=url,observed_on=DAY,source_type='Catálogo web oficial (captura)',retailer_sku=sku,stock_status='Desconocido',scope='Precio web consultado; puede variar por zona, fecha, cuenta o establecimiento'))
# DIA listings identified in the retailer's official category pages on 2026-11-23
for data in [
 ('Arroz extra Dia Arrozona 1 kg','Dia Arrozona','1 kg',1.15,'5873'),
 ('Arroz largo Dia Arrozona 1 kg','Dia Arrozona','1 kg',1.20,'250021'),
 ('Vasos de arroz Dia Al Punto 2 × 125 g','Dia Al Punto','2 × 125 g',1.05,'310496'),
 ('Arroz redondo J. Sendra Dia Arrozona 1 kg','Dia Arrozona','1 kg',1.60,'21415'),
 ('Arroz redondo SOS 1 kg','SOS','1 kg',1.88,'53397'),
 ('Arroz basmati Dia Selección Mundial 1 kg','Dia Selección Mundial','1 kg',2.10,'28809'),
 ('Arroz vaporizado Dia Arrozona 1 kg','Dia Arrozona','1 kg',1.55,'60069'),
 ('Vasos de arroz basmati Brillante 2 × 125 g','Brillante','2 × 125 g',1.35,'145913'),
 ('Vasos de arroz integral Brillante 2 × 125 g','Brillante','2 × 125 g',1.25,'267141'),
 ('Arroz tres delicias Dia Al Punto 850 g','Dia Al Punto','850 g',2.42,'142599')]:
    add('DIA','Arroz',*data[:3],data[3],DIA_RICE,data[4])
for data in [
 ('Leche semidesnatada Dia Láctea pack 6 × 1 l','Dia Láctea','6 × 1 l',4.98,'608P6'),
 ('Leche entera Dia Láctea pack 6 × 1 l','Dia Láctea','6 × 1 l',5.76,'607P6'),
 ('Leche desnatada Dia Láctea pack 6 × 1 l','Dia Láctea','6 × 1 l',4.86,'504'),
 ('Leche semidesnatada Dia Láctea 1 l','Dia Láctea','1 l',0.83,'271329'),
 ('Leche entera pasteurizada Dia Láctea 1 l','Dia Láctea','1 l',1.15,'608'),
 ('Leche entera Dia Láctea 1 l','Dia Láctea','1 l',0.96,'17548P6'),
 ('Leche semidesnatada Asturiana pack 6 × 1 l','Asturiana','6 × 1 l',7.02,'271330'),
 ('Leche semidesnatada pasteurizada Dia Láctea 1 l','Dia Láctea','1 l',1.09,'312953'),
 ('Leche entera Dia Láctea 3 × 200 ml','Dia Láctea','3 × 200 ml',0.92,'607'),
 ('Leche desnatada Dia Láctea 1 l','Dia Láctea','1 l',0.81,'17548')]:
    add('DIA','Lácteos',*data[:3],data[3],DIA_MILK,data[4])
for data in [
 ('Leche semidesnatada Carrefour brik 1 l','Carrefour','1 l',0.83),
 ('Leche entera Carrefour brik 1 l','Carrefour','1 l',0.96),
 ('Leche desnatada Carrefour brik 1 l','Carrefour','1 l',0.81),
 ('Leche semidesnatada Carrefour sin lactosa brik 1 l','Carrefour','1 l',0.94),
 ('Arroz largo categoría 1 Carrefour Classic 1 kg','Carrefour Classic','1 kg',1.20),
 ('Leche entera fresca Carrefour botella 1 l','Carrefour','1 l',1.15),
 ('Leche entera Carrefour botella 1,5 l','Carrefour','1,5 l',1.56)]:
    add('Carrefour','Arroz' if 'Arroz' in data[0] else 'Lácteos',*data,CARF)
# More product categories directly referenced on Carrefour official category/product pages.
CARF_EGGS='https://www.carrefour.es/supermercado/productoscrf-huevos-vinagre-blanco/F-1kc6vZ16muZ11dc/g'
CARF_OIL='https://www.carrefour.es/supermercado/productoscrf-carrefour-aceite-de-oliva-virgen-extra-lugar-fresco-y-seco-mollete/F-1kc6vZ10siZp646Z11fdZ1qgx/g'
for item in [
    ('Huevos frescos Carrefour El Mercado 24 ud.','Carrefour El Mercado','24 ud.',5.25),
    ('Huevos frescos Carrefour El Mercado 12 ud.','Carrefour El Mercado','12 ud.',3.05),
    ('Huevos de gallinas criadas en suelo Carrefour El Mercado 12 ud.','Carrefour El Mercado','12 ud.',2.85),
    ('Huevos de gallinas criadas en suelo Carrefour El Mercado 6 ud.','Carrefour El Mercado','6 ud.',1.69),
    ('Huevos frescos Carrefour El Mercado 12 ud. (segunda referencia)','Carrefour El Mercado','12 ud.',4.18)]:
    add('Carrefour','Huevos',*item,CARF_EGGS)
for item in [
    ('Aceite de oliva virgen extra Carrefour Extra 1 l','Carrefour Extra','1 l',4.34),
    ('Aceite de oliva virgen extra spray Carrefour Extra 200 ml','Carrefour Extra','200 ml',2.59),
    ('Aceite de oliva virgen extra Carrefour Extra 5 l','Carrefour Extra','5 l',20.22),
    ('Aceite de oliva virgen extra Carrefour Extra 750 ml','Carrefour Extra','750 ml',5.24),
    ('Aceite de oliva virgen extra Carrefour Extra 500 ml','Carrefour Extra','500 ml',3.35)]:
    add('Carrefour','Aceites',*item,CARF_OIL)
# Avoid dups in id
ids=[i['id'] for i in items];assert len(ids)==len(set(ids))
out=Path('/mnt/data/shopper_work/data')
out.mkdir(exist_ok=True)
(out/'retail_official_snapshot_2026-11-23.json').write_text(json.dumps({'capture_date':DAY,'provenance':'Fichas de categoría de webs oficiales; muestra editorial, no catálogo integral ni consulta a tienda física','licence_note':'Metadatos editoriales seleccionados; no redistribuir catálogos completos sin autorización','items':items},ensure_ascii=False,indent=2),encoding='utf8')
print(len(items))
