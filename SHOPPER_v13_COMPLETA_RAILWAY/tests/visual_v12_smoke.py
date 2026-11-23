import requests
from playwright.sync_api import sync_playwright

def proxy(route):
    req=route.request
    path=req.url.split('shopper.test',1)[1]
    hdr={k:v for k,v in req.headers.items() if k.lower() not in ('host','connection','content-length','accept-encoding')}
    resp=requests.request(req.method,'http://127.0.0.1:8791'+path,headers=hdr,data=req.post_data,timeout=14,allow_redirects=False)
    out={k:v for k,v in resp.headers.items() if k.lower() not in ('content-encoding','transfer-encoding','content-length','connection','date','server')}
    route.fulfill(status=resp.status_code,headers=out,body=resp.content)

with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('https://shopper.test/**',proxy)
 page.goto('https://shopper.test/',wait_until='domcontentloaded',timeout=15000)
 page.wait_for_timeout(1800)
 print('TITLE:',page.title())
 print('body:',page.locator('body').inner_text()[:240])
 print('errors:',errors[:8])
 page.screenshot(path='/mnt/data/SHOPPER_v12_movil.png',full_page=True)
 page.get_by_role('button',name='Explorar').first.click()
 page.wait_for_timeout(500)
 print('explore body:',page.locator('#main').inner_text()[:150])
 page.screenshot(path='/mnt/data/SHOPPER_v12_explorar_movil.png',full_page=True)
 page.get_by_role('button',name='Inicio').first.click()
 page.get_by_role('button',name='Cuenta',exact=True).first.click() if page.get_by_role('button',name='Cuenta',exact=True).count() else page.locator('.round-btn').click()
 page.get_by_role('button',name='Entrar',exact=True).click()
 page.locator('#authForm input[name=username]').fill('maria_demo')
 page.locator('#authForm input[name=password]').fill('ShopperDemo2026!')
 page.locator('#authForm button').first.click()
 page.wait_for_timeout(1300)
 print('after login:',page.locator('#main').inner_text()[:200])
 print('errors after login:',errors[:15])
 page.screenshot(path='/mnt/data/SHOPPER_v12_cestas_movil.png',full_page=True)
 b.close()
