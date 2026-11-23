import requests
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

def proxy(route):
    req=route.request
    path=req.url.split('shopper.test',1)[1]
    hdr={k:v for k,v in req.headers.items() if k.lower() not in ('host','connection','content-length','accept-encoding')}
    resp=requests.request(req.method,'http://127.0.0.1:8765'+path,headers=hdr,data=req.post_data,timeout=10,allow_redirects=False)
    out={k:v for k,v in resp.headers.items() if k.lower() not in ('content-encoding','transfer-encoding','content-length','connection','date','server')}
    route.fulfill(status=resp.status_code,headers=out,body=resp.content)

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=b.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.route('https://shopper.test/**',proxy)
    page.goto('https://shopper.test/',wait_until='domcontentloaded',timeout=12000)
    page.wait_for_timeout(1200)
    print('TITLE',page.title(),'mainlen',len(page.locator('#main').inner_text()))
    print('PAGE ERRORS',errors[:5])
    page.screenshot(path='/mnt/data/SHOPPER_v11_movil.png',full_page=True)
    b.close()
