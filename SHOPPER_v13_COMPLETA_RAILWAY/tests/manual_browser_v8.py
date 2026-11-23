"""V8 browser test with real TestClient API routed through an isolated browser bridge.
Chromium is denied TCP loopback in this sandbox. This tests the full browser DOM,
network requests via a Python in-process FastAPI TestClient, and all UI workflows.
"""
import os,sys, json, re, tempfile, traceback
from pathlib import Path
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
os.environ['SHOPPER_DB']=str(Path(tempfile.mkdtemp(prefix='shopper8_'))/'test.sqlite3')
os.environ['SHOPPER_DEMO']='1'
sys.path.insert(0,str(ROOT))
import main
backend=TestClient(main.app)

def relay(_source,data):
    url=data['url']
    headers=data.get('headers',{})
    method=data.get('method','GET')
    kwargs={'headers':headers}
    if data.get('body') is not None:kwargs['content']=data['body']
    response=backend.request(method,url,**kwargs)
    try: parsed=response.json()
    except Exception:parsed={'detail':response.text}
    return {'status':response.status_code,'data':parsed}

HTML=(ROOT/'static'/'index.html').read_text()
HTML=re.sub(r'<script src="/static/app.js" defer></script>','',HTML)
HTML=re.sub(r'<link rel="stylesheet" href="/static/style.css">','',HTML)
CSS=(ROOT/'static'/'style.css').read_text()
JS=(ROOT/'static'/'app.js').read_text()
BRIDGE='''window.fetch=async (url,init={})=>{const r=await window.__apiBridge({url:String(url),method:init.method||'GET',headers:init.headers||{},body:init.body??null});return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data,blob:async()=>new Blob([JSON.stringify(r.data)])};};'''

def new_page(browser,width,height,mobile=False):
    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1,is_mobile=mobile,has_touch=mobile)
    page.expose_binding('__apiBridge',relay)
    page.set_content(HTML,wait_until='domcontentloaded')
    page.add_style_tag(content=CSS)
    page.add_script_tag(content="const memory = new Map(); Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)}});")
    page.add_script_tag(content=BRIDGE)
    page.add_script_tag(content=JS)
    return page

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=new_page(browser,1390,920)
    errors=[]
    page.on('pageerror',lambda exc:errors.append(str(exc)))
    page.locator('[data-demo="maria_demo"]').click()
    try:page.locator('.intro-hero').wait_for(timeout=3000)
    except Exception:
        print('ERRORS', errors, 'TOAST',page.locator('#toast').inner_text(),'AUTH',page.locator('#authScreen').get_attribute('class'),'TOKEN',page.evaluate('sessionStorage.getItem("shopper_v8_token")'), 'FETCH',page.evaluate('typeof window.fetch'))
        raise
    page.screenshot(path='/mnt/data/SHOPPER_v8_escritorio.png',full_page=True)
    # Community shelf: store observation, photo-free and attributable
    page.locator('[data-nav="stores"]').first.click()
    page.locator('[data-action="openShelf"]').first.click()
    page.locator('#shelfPanel').wait_for()
    page.locator('#shelfObserve [name=product_id]').select_option('1')
    page.locator('#shelfObserve [name=note]').fill('Producto visto durante un test')
    page.locator('#shelfObserve button').click()
    page.locator('#shelfPanel').get_by_text('Nutella 400 g').first.wait_for()
    page.locator('#shelfPanel [data-action="watchShelfProduct"]').first.click()
    page.locator('[data-nav="watch"]').first.click()
    page.get_by_text('Seguimiento de productos').wait_for()
    assert page.get_by_text('Nutella 400 g').count()>0
    page.screenshot(path='/mnt/data/SHOPPER_v8_seguimientos.png',full_page=True)
    # Pantry partial consumption
    page.locator('[data-nav="pantry"]').first.click()
    page.locator('#pantryAdd [name=custom_name]').fill('Yogures prueba')
    page.locator('#pantryAdd [name=quantity]').fill('4')
    page.locator('#pantryAdd button').click()
    page.locator('[data-portion]').first.fill('1')
    page.locator('[data-action="pantryPortion"][data-status="used"]').first.click()
    page.get_by_text('3 ud',exact=False).first.wait_for(timeout=5000)
    # Weekly reusable list => current
    page.locator('[data-nav="baskets"]').first.click()
    page.locator('#createBasket [name=title]').fill('Semanal para probar')
    page.locator('#createBasket [name=kind]').select_option('semanal')
    page.locator('#createBasket button').click()
    page.locator('#quickItem [name=title]').fill('Arroz')
    page.locator('#quickItem button').click()
    page.once('dialog',lambda d:d.accept())
    page.locator('[data-action="copyActual"]').click()
    page.get_by_text('Arroz').first.wait_for()
    # Purchase expense and time log
    page.locator('[data-nav="history"]').first.click()
    page.locator('#shoppingRunAdd [name=paid_eur]').fill('18.55')
    page.locator('#shoppingRunAdd button').click()
    page.get_by_text('18,55',exact=False).first.wait_for(timeout=5000)
    page.screenshot(path='/mnt/data/SHOPPER_v8_historial.png',full_page=True)
    # Mobile layout
    mobile=new_page(browser,390,844,mobile=True)
    mobile.on('pageerror',lambda exc:errors.append('Mobile: '+str(exc)))
    mobile.locator('[data-demo="maria_demo"]').click()
    mobile.locator('.intro-hero').wait_for()
    mobile.screenshot(path='/mnt/data/SHOPPER_v8_movil.png',full_page=True)
    print('Completed visual flows; JS errors:',errors)
    assert not errors,errors
    browser.close()
