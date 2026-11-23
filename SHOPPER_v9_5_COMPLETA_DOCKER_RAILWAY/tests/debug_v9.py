"""Real Chromium UI interactions with TestClient via JS bridge (browser network restricted).
This tests rendering/clicks/forms against the same FastAPI backend, without claiming public HTTPS.
"""
from pathlib import Path
import os,sys,secrets
ROOT=Path(__file__).resolve().parents[1]
os.environ['SHOPPER_DB']='/tmp/shopper_v9_browser_'+secrets.token_hex(4)+'.sqlite3'
os.environ['SHOPPER_DEMO']='0';os.environ['SHOPPER_REMOTE']='0'
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
html=(ROOT/'static/index.html').read_text(encoding='utf-8')
css=(ROOT/'static/style.css').read_text(encoding='utf-8')
js=(ROOT/'static/app.js').read_text(encoding='utf-8')
html=html.replace('<link rel="stylesheet" href="/static/style.css">','<style>'+css+'</style>')
html=html.replace('<script src="/static/app.js" defer></script>','')
html=html.replace('<link rel="icon" href="/static/icon.svg" type="image/svg+xml">','').replace('<link rel="manifest" href="/static/manifest.webmanifest">','')

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 a=browser.new_context(viewport={'width':1440,'height':940})
 b=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 contexts=[]
 for ctx in (a,b):
    client=TestClient(__import__('main').app)
    page=ctx.new_page()
    def bridge(data,client=client):
        h=data.get('headers') or {}
        return (lambda r: {'status':r.status_code,'body':r.json() if 'application/json' in r.headers.get('content-type','') else {}})(
          client.request(data['method'],data['url'],headers=h,content=data.get('body')))
    page.expose_function('apiBridge',bridge)
    page.set_content(html,wait_until='load')
    page.evaluate('''() => {
      window.fetch = async (url,opt={}) => {
       const r = await window.apiBridge({url:String(url),method:opt.method||'GET',headers:opt.headers||{},body:opt.body||null});
       return new Response(JSON.stringify(r.body),{status:r.status,headers:{'content-type':'application/json'}});
      };
      window.EventSource = class {constructor(){} addEventListener(){} close(){}};
    }''')
    page.add_script_tag(content=js)
    contexts.append((ctx,page))
 pa=contexts[0][1];pb=contexts[1][1]
 errors=[]
 pa.on('pageerror',lambda e:errors.append('desktop '+str(e)))
 pb.on('pageerror',lambda e:errors.append('mobile '+str(e)))
 for page,name in [(pa,'maria_'+secrets.token_hex(3)),(pb,'lucas_'+secrets.token_hex(3))]:
    page.locator('#showRegister').click()
    page.wait_for_timeout(400)
    print('DEBUG JS',page.evaluate("() => ({click:typeof clickAction,boot:typeof boot,fetch:typeof fetch,toast:document.querySelector('#toast').textContent})"))
    print('CALL DIRECT',page.evaluate("async () => {await clickAction({target:document.getElementById('showRegister')});return document.getElementById('registerForm').className}"))
    print('DEBUG FORM',page.evaluate("() => ({form:document.querySelector('#registerForm').className, login:document.querySelector('#loginForm').className, button:document.querySelector('#showRegister').className, html:document.querySelector('#authScreen').className})"))
    page.screenshot(path='/mnt/data/SHOPPER_v9_debug.png')
    browser.close()
    raise SystemExit
    page.locator('#registerForm input[name="username"]').fill(name)
    page.locator('#registerForm input[name="display_name"]').fill(name)
    page.locator('#registerForm input[name="password"]').fill('ExtraSecurePassword2026!')
    page.locator('#registerForm button[type="submit"]').click()
    page.locator('#appShell:not(.hidden)').wait_for(timeout=15000)
    assert page.locator('.home-hero').count()==1
 pa.screenshot(path='/mnt/data/SHOPPER_v9_escritorio.png',full_page=True)
 pb.screenshot(path='/mnt/data/SHOPPER_v9_iphone.png',full_page=True)
 pa.locator('#desktopNav [data-nav="baskets"]').click()
 pa.locator('#createBasket input[name="title"]').fill('Compra en familia')
 pa.locator('#createBasket button').click()
 pa.locator('#quickItem input[name="title"]').fill('Pan integral')
 pa.locator('#quickItem button').click()
 pa.locator('[data-action="basketInvite"][data-role="editor"]').click()
 code=pa.locator('.invite-spot .codebox').inner_text().strip()
 pb.locator('.bottom-nav [data-nav="baskets"]').click()
 pb.locator('#redeemInvitation input[name="code"]').fill(code)
 pb.locator('#redeemInvitation button').click()
 pb.locator('[data-open-basket]').filter(has_text='Compra en familia').first.click()
 pb.get_by_text('Pan integral').first.wait_for(timeout=8000)
 pb.locator('#quickItem input[name="title"]').fill('Aceite de oliva')
 pb.locator('#quickItem button').click()
 pa.locator('[data-action="refreshBasket"]').click()
 pa.get_by_text('Aceite de oliva').first.wait_for(timeout=10000)
 pa.locator('#desktopNav [data-nav="circle"]').click()
 pa.locator('#familyTaskCreate input[name="title"]').fill('Comprar para la abuela')
 pa.locator('#familyTaskCreate select[name="basket_id"]').select_option(label='Compra en familia')
 pa.locator('#familyTaskCreate button').click()
 pa.get_by_text('Comprar para la abuela').first.wait_for(timeout=10000)
 pb.locator('.bottom-nav [data-nav="circle"]').click()
 pb.get_by_text('Comprar para la abuela').first.wait_for(timeout=10000)
 pb.locator('[data-action="taskState"][data-status="accepted"]').click()
 pb.get_by_text('En marcha').first.wait_for(timeout=10000)
 pb.screenshot(path='/mnt/data/SHOPPER_v9_circulo_iphone.png',full_page=True)
 if errors:raise AssertionError(errors)
 print('BROWSER SUCCESS: 2 profiles, invitation, live shared basket after refresh, family task and mobile screen')
 browser.close()
