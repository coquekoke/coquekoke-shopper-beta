"""Playwright browser via a local TestClient network interception, because sandbox blocks localhost in Chromium."""
from pathlib import Path
import os,sys,secrets
os.environ['SHOPPER_DB']='/tmp/shopper_v9_bridge_'+secrets.token_hex(3)+'.sqlite3'
os.environ['SHOPPER_REMOTE']='0';os.environ['SHOPPER_DEMO']='0';os.environ['SHOPPER_ALLOWED_HOSTS']='shopper.test'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import main
from playwright.sync_api import sync_playwright
BASE='https://shopper.test'

def route_hook(client):
 def hook(route):
    req=route.request
    url=req.url.split('shopper.test',1)[-1]
    if url.startswith('/api/baskets/') and url.endswith('/events'):
        return route.fulfill(status=200,headers={'content-type':'text/event-stream','cache-control':'no-cache'},body=': connected\n\n')
    headers={k:v for k,v in req.headers.items() if k.lower() not in ('content-length','connection','accept-encoding','origin')}
    headers['host']='shopper.test'
    try:
      resp=client.request(req.method,url,headers=headers,content=req.post_data_buffer,follow_redirects=False)
      allowed={'content-type','cache-control','set-cookie','location','content-security-policy'}
      resheaders={k:v for k,v in resp.headers.items() if k.lower() in allowed}
      return route.fulfill(status=resp.status_code,headers=resheaders,body=resp.content)
    except Exception as e:
      print('ROUTE FAIL:',req.method,url,e)
      route.abort()
 return hook

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 a=browser.new_context(viewport={'width':1440,'height':940},device_scale_factor=1)
 b=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
 a.route('**/*',route_hook(TestClient(main.app,base_url=BASE)))
 b.route('**/*',route_hook(TestClient(main.app,base_url=BASE)))
 pa=a.new_page();pb=b.new_page()
 for page,name in [(pa,'maria_'+secrets.token_hex(3)),(pb,'lucas_'+secrets.token_hex(3))]:
    page.goto(BASE,wait_until='domcontentloaded',timeout=20000)
    page.locator('#showRegister').click(timeout=10000)
    page.locator('#registerForm input[name="username"]').fill(name)
    page.locator('#registerForm input[name="display_name"]').fill(name)
    page.locator('#registerForm input[name="password"]').fill('ExtraSecurePassword2026!')
    page.locator('#registerForm button[type="submit"]').click()
    page.locator('#appShell:not(.hidden)').wait_for(timeout=20000)
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
 assert pb.get_by_text('Pan integral').count()>=1
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
 print('BROWSER SUCCESS: two isolated profiles, invite, sharing, items and family task')
 browser.close()
