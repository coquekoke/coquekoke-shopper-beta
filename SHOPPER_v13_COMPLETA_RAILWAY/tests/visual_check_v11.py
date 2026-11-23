from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=b.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.goto('http://127.0.0.1:8765/',wait_until='domcontentloaded',timeout=12000)
    page.wait_for_timeout(1500)
    print('TITLE',page.title())
    print('HEADER',page.locator('#main').inner_text()[:300])
    print('PAGE ERRORS',errors[:5])
    page.screenshot(path='/mnt/data/SHOPPER_v11_movil.png',full_page=True)
    b.close()
