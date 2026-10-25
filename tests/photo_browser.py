"""Real-browser photo gallery, mobile preview/retry, persistence and access checks."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw
import requests
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from campuslink.seed import PASSWORD, seed

ROOT=Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-photos-') as temp:
        temp=Path(temp)
        database=temp/'photos.sqlite3'
        seed(database)
        for name,color in [('one','#43283F'),('two','#597f6d'),('three','#666da2'),('four','#98674c'),('replacement','#934f72')]:
            image=Image.new('RGB',(600,800),color)
            draw=ImageDraw.Draw(image)
            draw.rounded_rectangle((90,180,510,620),radius=75,outline='white',width=6)
            draw.text((230,390),'TEST '+name,fill='white',font_size=24)
            image.save(temp/(name+'.png'))
        (temp/'invalid.png').write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}'
        env={**os.environ,'CAMPUSLINK_DB':str(database),'CAMPUSLINK_MODE':'local'}
        drivers=[]
        server=None
        output=ROOT/'artifacts'
        output.mkdir(exist_ok=True)
        with open(temp/'server.log','w+') as log:
            def start():
                nonlocal server
                server=subprocess.Popen([os.getenv('CAMPUSLINK_TEST_PYTHON',sys.executable),'-m','uvicorn','campuslink.app:app','--host','127.0.0.1','--port',str(port),'--timeout-graceful-shutdown','2','--log-level','warning'],cwd=ROOT,env=env,stdout=log,stderr=log)
                for _ in range(100):
                    try:
                        if requests.get(url+'/api/health',timeout=.5).ok:
                            return
                    except requests.RequestException:
                        pass
                    time.sleep(.1)
                raise RuntimeError('Photo test server did not start.')

            def browser(mobile=False):
                options=Options()
                options.binary_location=shutil.which('chromium') or shutil.which('google-chrome')
                for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--window-size=1280,1000']:
                    options.add_argument(flag)
                options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
                driver=webdriver.Chrome(service=Service(shutil.which('chromedriver')),options=options)
                if mobile:
                    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
                drivers.append(driver)
                return driver

            def wait(driver,selector):
                return WebDriverWait(driver,15).until(EC.presence_of_element_located((By.CSS_SELECTOR,selector)))

            def click(driver,selector):
                def attempt(_):
                    button=EC.element_to_be_clickable((By.CSS_SELECTOR,selector))(driver)
                    if not button:return False
                    driver.execute_script('arguments[0].scrollIntoView({block:"center"})',button)
                    button.click()
                    return True
                WebDriverWait(driver,15,ignored_exceptions=(StaleElementReferenceException,)).until(attempt)

            def text(driver,expected):
                WebDriverWait(driver,15).until(lambda _:expected in driver.find_element(By.TAG_NAME,'body').text)

            def fetch(driver,endpoint):
                return driver.execute_async_script('const done=arguments[arguments.length-1];fetch(arguments[0]).then(async r=>done({status:r.status,body:r.headers.get("content-type").includes("json")?await r.json():null})).catch(e=>done({error:String(e)}));',endpoint)

            def me(driver):
                return fetch(driver,'/api/me')['body']['user']

            def login(driver,name):
                driver.get(url+'/login')
                wait(driver,'[name=email]').send_keys(name+'@campuslink.test')
                driver.find_element(By.NAME,'password').send_keys(PASSWORD)
                click(driver,'#auth-form button[type=submit]')
                wait(driver,'.dating-welcome')
                click(driver,'a[href="/profile"][data-nav]')
                wait(driver,'#photo-manager')

            def gallery_count(driver,count):
                WebDriverWait(driver,15).until(lambda _:len(driver.find_elements(By.CSS_SELECTOR,'.photo-tile'))==count and driver.find_element(By.ID,'photo-manager').get_attribute('aria-busy')=='false')

            def choose(driver,name):
                wait(driver,'#profile-photo-file').send_keys(str(temp/(name+'.png')))
                wait(driver,'.photo-upload-preview img')

            def upload(driver,name,count):
                choose(driver,name)
                click(driver,'[data-photo-action=upload]')
                gallery_count(driver,count)
                WebDriverWait(driver,15).until(lambda _:not driver.find_elements(By.CSS_SELECTOR,'.photo-upload-preview'))

            def loaded(driver,selector):
                WebDriverWait(driver,15).until(lambda _:driver.execute_script('const i=document.querySelector(arguments[0]);return !!i && i.complete && i.naturalWidth>0;',selector))

            def activate(driver):
                click(driver,'[data-action=dating-settings]')
                click(driver,'#dating-form [name=dating_enabled]')
                click(driver,'#dating-form button[type=submit]')
                wait(driver,'.dating-card')

            def search(driver,name):
                field=wait(driver,'#student-search')
                field.clear();field.send_keys(name)
                WebDriverWait(driver,15).until(lambda _:len(driver.find_elements(By.CSS_SELECTOR,'.dating-card'))==1 and name in driver.find_element(By.CSS_SELECTOR,'.dating-card h3').text)

            try:
                start()
                alice,brian=browser(mobile=True),browser()
                login(alice,'alice')
                bio=wait(alice,'#profile-form [name=bio]')
                bio.clear();bio.send_keys('A draft must survive photo changes.')
                upload(alice,'one',1)
                first=me(alice)['photos'][0]['id']
                loaded(alice,'.topbar .avatar-photo')
                assert alice.find_element(By.CSS_SELECTOR,'#profile-form [name=bio]').get_attribute('value')=='A draft must survive photo changes.'
                upload(alice,'two',2)
                second=me(alice)['photos'][1]['id']
                click(alice,f'[data-photo-id="{second}"] [data-photo-action=main]')
                WebDriverWait(alice,15).until(lambda _:alice.execute_script('return document.querySelector(".photo-tile")?.dataset.photoId')==second)
                click(alice,f'[data-photo-id="{second}"] [data-photo-action=later]')
                WebDriverWait(alice,15).until(lambda _:alice.find_element(By.CSS_SELECTOR,'.photo-tile').get_attribute('data-photo-id')==first)
                old_url=me(alice)['main_photo_url']
                click(alice,f'[data-photo-id="{first}"] [data-photo-action=replace]')
                choose(alice,'replacement')
                click(alice,'[data-photo-action=upload]')
                gallery_count(alice,2)
                WebDriverWait(alice,15).until(lambda _:me(alice)['main_photo_url']!=old_url)
                print('PASS: mobile preview/upload, main selection, reordering and replacement; unsaved profile text survives',flush=True)

                choose(alice,'three')
                alice.execute_cdp_cmd('Network.enable',{})
                alice.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
                click(alice,'[data-photo-action=upload]')
                text(alice,'Retry upload')
                assert alice.find_elements(By.CSS_SELECTOR,'.photo-upload-preview')
                alice.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
                click(alice,'[data-photo-action=upload]')
                gallery_count(alice,3)
                assert len({photo['id'] for photo in me(alice)['photos']})==3
                choose(alice,'invalid')
                click(alice,'[data-photo-action=upload]')
                text(alice,'not a valid still JPEG, PNG, or WebP image')
                gallery_count(alice,3)
                click(alice,'[data-photo-action=cancel]')
                upload(alice,'four',4)
                assert not alice.find_elements(By.ID,'profile-photo-file')
                assert not alice.execute_script('return document.documentElement.scrollWidth>innerWidth')
                alice.save_screenshot(str(output/'photo-gallery-mobile.png'))
                click(alice,'#profile-form button[type=submit]')
                text(alice,'Profile and preferences saved.')
                gallery_count(alice,4)
                print('PASS: offline retry, invalid-file rejection, four-photo limit and 390px layout',flush=True)

                persisted=me(alice)['photos']
                server.kill();server.wait(timeout=10)
                start()
                alice.refresh()
                gallery_count(alice,4)
                assert me(alice)['photos']==persisted
                loaded(alice,'.photo-tile img')
                print('PASS: gallery records, image bytes and session survive a server crash and browser refresh',flush=True)

                login(brian,'brian')
                upload(brian,'two',1)
                program=wait(brian,'#profile-form [name=program]')
                program.clear();program.send_keys('Information Technology')
                click(brian,'#profile-form button[type=submit]')
                text(brian,'Profile and preferences saved.')
                activate(alice)
                activate(brian)
                search(alice,'Brian')
                loaded(alice,'.dating-photo img')
                click(alice,'.dating-card .name-button')
                wait(alice,'#dialog .profile-photo-gallery img')
                loaded(alice,'#dialog .profile-photo-gallery img')
                click(alice,'#dialog [data-action=view-photo]')
                loaded(alice,'#dialog .photo-lightbox')
                click(alice,'#dialog [data-action=close-dialog]')
                click(alice,'.dating-card [data-action=like]')
                text(alice,'No more profiles for now.')
                search(brian,'Alice')
                loaded(brian,'.dating-photo img')
                click(brian,'.dating-card [data-action=like]')
                text(brian,'It’s a match.')
                click(brian,'#dialog [data-action=open-chat]')
                loaded(brian,'.chat-header .avatar-photo')
                click(alice,'[data-action=view-dating-matches]')
                loaded(alice,'.connection-card .avatar-photo')
                click(alice,'[data-action=open-chat]')
                loaded(alice,'.chat-header .avatar-photo')
                print('PASS: photos render in cross-program Dating discovery, full profiles, photo viewer, matches and chat',flush=True)

                wait(brian,'#message-input').send_keys('A chat draft must survive a new main photo.')
                click(alice,'a[href="/profile"][data-nav]')
                gallery_count(alice,4)
                click(alice,f'[data-photo-id="{second}"] [data-photo-action=main]')
                WebDriverWait(alice,15).until(lambda _:alice.execute_script('return document.querySelector(".photo-tile")?.dataset.photoId')==second)
                new_main=me(alice)['main_photo_url']
                WebDriverWait(brian,15).until(lambda _:brian.find_element(By.CSS_SELECTOR,'.chat-header .avatar-photo').get_attribute('src').endswith(new_main))
                assert brian.find_element(By.ID,'message-input').get_attribute('value')=='A chat draft must survive a new main photo.'
                alice.save_screenshot(str(output/'photo-profile-mobile.png'))
                click(alice,'a[href="/chats"][data-nav]')
                loaded(alice,'.chat-header .avatar-photo')
                click(alice,'#chat-safety > summary')
                click(alice,'[data-action=confirm-block-dialog]')
                click(alice,'[data-action=block-student]')
                WebDriverWait(brian,15).until(lambda _:not brian.find_elements(By.CSS_SELECTOR,'#composer'))
                assert fetch(brian,new_main)['status']==404
                print('PASS: live avatar updates preserve chat drafts; blocking revokes direct image access',flush=True)

                click(alice,'a[href="/profile"][data-nav]')
                for count in (3,2,1,0):
                    click(alice,'.photo-tile [data-photo-action=remove]')
                    gallery_count(alice,count)
                assert me(alice)['main_photo_url'] is None
                assert not alice.find_elements(By.CSS_SELECTOR,'.topbar .avatar-photo')
                assert fetch(alice,new_main)['status']==404
                print('PASS: deleting the gallery removes stored images and restores initials',flush=True)
                for driver in drivers:
                    errors=[entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ['Uncaught','SyntaxError','violates the following Content Security Policy'])]
                    assert not errors,errors
            except BaseException:
                for index,driver in enumerate(drivers):
                    try:
                        driver.save_screenshot(str(output/f'photo-failure-{index}.png'))
                        print('BROWSER',index,driver.current_url,driver.find_element(By.TAG_NAME,'body').text[-4500:],driver.get_log('browser'),flush=True)
                        print('Gallery state:',me(driver).get('photos'),flush=True)
                    except Exception:pass
                log.flush();log.seek(0);print(log.read()[-4000:])
                raise
            finally:
                for driver in drivers:driver.quit()
                if server and server.poll() is None:
                    server.terminate()
                    try:server.wait(timeout=8)
                    except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':
    run()
