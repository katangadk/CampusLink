"""Real Chromium, separate accounts, real HTTP/SSE, persistence and offline retry.

Run: python3 -m tests.browser_smoke
Requires local Chromium + chromedriver and Selenium. Uses an isolated temporary DB.
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException

from campuslink.seed import PASSWORD, seed

ROOT=Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-browser-') as temp:
        db=Path(temp)/'browser.sqlite3'
        seed(db)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}'
        env={**os.environ,'CAMPUSLINK_DB':str(db),'CAMPUSLINK_MODE':'local'}
        log=open(Path(temp)/'server.log','w+')
        process=None
        drivers=[]

        def start():
            nonlocal process
            process=subprocess.Popen([sys.executable,'-m','uvicorn','campuslink.app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
            for _ in range(100):
                try:
                    if requests.get(url+'/api/health',timeout=.5).ok:
                        return
                except requests.RequestException:
                    pass
                time.sleep(.1)
            raise RuntimeError('Test server did not start.')

        def browser(width=1440,height=1050):
            options=Options()
            options.binary_location=shutil.which('chromium') or shutil.which('google-chrome')
            for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--no-proxy-server',f'--window-size={width},{height}']:
                options.add_argument(flag)
            options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
            d=webdriver.Chrome(service=Service(shutil.which('chromedriver')),options=options)
            drivers.append(d)
            return d

        def wait(d, selector):
            return WebDriverWait(d,15).until(EC.presence_of_element_located((By.CSS_SELECTOR,selector)))

        def click(d, selector):
            def attempt(_):
                e=EC.element_to_be_clickable((By.CSS_SELECTOR,selector))(d)
                if not e:
                    return False
                d.execute_script('arguments[0].scrollIntoView({block:"center"})',e)
                e.click()
                return True
            WebDriverWait(d,15,ignored_exceptions=(StaleElementReferenceException,)).until(attempt)

        def has_text(d,text):
            WebDriverWait(d,15).until(lambda _:text in d.find_element(By.TAG_NAME,'body').text)

        def login(d,name):
            d.get(url+'/login')
            wait(d,'[name=email]').send_keys(name+'@campuslink.test')
            d.find_element(By.NAME,'password').send_keys(PASSWORD)
            click(d,'#auth-form button[type=submit]')
            wait(d,'[data-action=discover-mode][data-mode=for-you]')
            click(d,'[data-action=discover-mode][data-mode=for-you]')
            wait(d,'.student-card')

        def discover_brian(d):
            click(d,'[data-action=discover-mode][data-mode=friend]')
            wait(d,'#student-search').send_keys('brian')
            has_text(d,'Brian Mwansa')
            WebDriverWait(d,15).until(lambda _:len(d.find_elements(By.CSS_SELECTOR,'.student-card'))==1)

        def open_first_chat(d):
            click(d,'a[href="/chats"][data-nav]')
            click(d,'.conversation-item')
            wait(d,'#message-input')

        def send(d,body):
            wait(d,'#message-input').send_keys(body)
            click(d,'#composer button[type=submit]')
            WebDriverWait(d,15).until(lambda _:not d.find_element(By.ID,'message-input').get_attribute('value'))

        try:
            start()
            alice,brian=browser(),browser()
            alice.get(url)
            has_text(alice,'Meet students.')
            out=ROOT/'artifacts'
            out.mkdir(exist_ok=True)
            alice.save_screenshot(str(out/'landing-desktop.png'))
            login(alice,'alice')
            alice.save_screenshot(str(out/'discovery-desktop.png'))
            discover_brian(alice)
            click(alice,'[data-action=connect][data-kind=friend]')
            has_text(alice,'A little quiet here.')
            login(brian,'brian')
            click(brian,'a[href="/matches"][data-nav]')
            click(brian,'a[href="/connections"][data-nav]')
            has_text(brian,'Alice Banda')
            click(brian,'[data-command=accept]')
            has_text(brian,'No requests just yet.')
            open_first_chat(alice)
            open_first_chat(brian)
            wait(brian,'#message-input').send_keys('A draft that must survive updates')
            payload='Hello Brian <script>window.pwned=true</script>'
            send(alice,payload)
            has_text(brian,payload)
            assert brian.find_element(By.ID,'message-input').get_attribute('value')=='A draft that must survive updates'
            assert brian.execute_script('return window.pwned') is None
            assert len(brian.find_elements(By.CSS_SELECTOR,'.bubble'))==1
            brian.find_element(By.ID,'message-input').clear()
            send(brian,'Hi Alice! Yes, let’s study algorithms.')
            has_text(alice,'Hi Alice! Yes, let’s study algorithms.')
            alice.save_screenshot(str(out/'chat-desktop.png'))
            print('PASS: discover → request → accept → bidirectional real-time chat; draft preservation; safe text rendering',flush=True)

            # A failed send retains its ID and text; retry must create exactly one record.
            alice.execute_cdp_cmd('Network.enable',{})
            alice.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
            wait(alice,'#message-input').send_keys('One offline retry, one message')
            click(alice,'#composer button[type=submit]')
            has_text(alice,'Send failed · Retry')
            alice.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
            click(alice,'[data-action=retry-message]')
            has_text(brian,'One offline retry, one message')
            assert sum(e.text=='One offline retry, one message' for e in brian.find_elements(By.CSS_SELECTOR,'.bubble'))==1
            print('PASS: offline failed-send retention and idempotent retry',flush=True)

            # Keep browser sessions alive through a real server restart.
            process.kill();process.wait(timeout=10)
            start()
            send(brian,'Still here after a restart')
            has_text(alice,'Still here after a restart')
            alice.refresh()
            click(alice,'.conversation-item')
            has_text(alice,'Still here after a restart')
            print('PASS: database/session persistence and SSE reconnect after server restart',flush=True)

            # Revoke authorization through the UI and observe the other live client.
            click(brian,'#chat-safety > summary')
            click(brian,'#chat-safety [data-action=confirm-block-dialog]')
            click(brian,'[data-action=block-student]')
            WebDriverWait(alice,15).until(lambda _:not alice.find_elements(By.CSS_SELECTOR,'#composer'))
            assert not brian.find_elements(By.CSS_SELECTOR,'#composer')
            print('PASS: blocking closes conversations on both clients',flush=True)

            alice.set_window_size(390,844)
            click(alice,'a[href="/discover"][data-nav]')
            click(alice,'[data-action=discover-mode][data-mode=for-you]')
            wait(alice,'#student-search')
            alice.save_screenshot(str(out/'discovery-mobile.png'))
            assert alice.execute_script('return document.documentElement.scrollWidth <= innerWidth')
            assert all(e.is_displayed() for e in alice.find_elements(By.CSS_SELECTOR,'.nav a'))
            # Persist privacy/profile changes and exercise reporting and role-based UI.
            click(alice,'a[href="/profile"][data-nav]')
            bio=wait(alice,'#profile-form [name=bio]')
            bio.clear();bio.send_keys('Browser-tested profile update')
            click(alice,'#profile-form button[type=submit]')
            alice.refresh()
            assert wait(alice,'#profile-form [name=bio]').get_attribute('value')=='Browser-tested profile update'
            click(alice,'a[href="/discover"][data-nav]')
            click(alice,'[data-action=discover-mode][data-mode=for-you]')
            # Clear search through its actual input even when the filter panel is closed.
            search=wait(alice,'#student-search');search.clear();search.send_keys('chipo')
            has_text(alice,'Chipo Phiri')
            click(alice,'.student-card [data-action=student-menu]')
            click(alice,'#dialog [data-action=profile-safety-dialog]')
            click(alice,'#dialog [data-action=report-profile]')
            wait(alice,'#report-form [name=detail]').send_keys('Browser moderation workflow test')
            click(alice,'#report-form button[type=submit]')
            has_text(alice,'Report received.')
            click(alice,'[data-action=close-dialog]')
            click(brian,'a[href="/profile"][data-nav]')
            click(brian,'[data-action=logout]')
            wait(brian,'#auth-form')
            login(brian,'moderator')
            click(brian,'a[href="/profile"][data-nav]')
            click(brian,'[data-action=moderation]')
            has_text(brian,'Browser moderation workflow test')
            click(brian,'[data-action=moderate][data-command=resolve]')
            click(alice,'a[href="/profile"][data-nav]')
            click(alice,'[data-action=my-reports]')
            has_text(alice,'resolved')
            click(alice,'[data-action=close-dialog]')
            print('PASS: profile persistence, private report submission, moderator review and reporter status',flush=True)

            # A genuinely new account must complete the progressive onboarding flow.
            click(brian,'[data-action=logout]')
            wait(brian,'#auth-form')
            brian.get(url+'/signup')
            for name,value in {'display_name':'Browser Student','username':'browser_student','email':'browser@campuslink.test','password':PASSWORD}.items():
                wait(brian,f'#auth-form [name={name}]').send_keys(value)
            click(brian,'#auth-form [name=agreement]')
            click(brian,'#auth-form button[type=submit]')
            has_text(brian,'Step 1 of 6')
            wait(brian,'[name=bio]').send_keys('Onboarding draft preserved')
            click(brian,'#onboarding-form button[type=submit]:not([name=back])')
            has_text(brian,'Step 2 of 6')
            wait(brian,'[name=program]').send_keys('Computer Science')
            wait(brian,'[name=subjects]').send_keys('Algorithms, Python')
            click(brian,'#onboarding-form button[type=submit]:not([name=back])')
            has_text(brian,'Step 3 of 6')
            click(brian,'[name=back]')
            has_text(brian,'Step 2 of 6')
            assert wait(brian,'[name=program]').get_attribute('value')=='Computer Science'
            click(brian,'#onboarding-form button[type=submit]:not([name=back])')
            has_text(brian,'Step 3 of 6')
            click(brian,'.interest-option input[value=Programming] + span')
            for step in (4,5,6):
                click(brian,'#onboarding-form button[type=submit]:not([name=back])')
                has_text(brian,f'Step {step} of 6')
            click(brian,'#onboarding-form button[type=submit]:not([name=back])')
            wait(brian,'[data-action=discover-mode][data-mode=for-you]')
            click(brian,'[data-action=discover-mode][data-mode=for-you]')
            wait(brian,'.student-card')
            click(brian,'a[href="/profile"][data-nav]')
            click(brian,'[data-action=dating-settings]')
            has_text(brian,'Dating is unavailable until adult eligibility is established.')
            print('PASS: registration, six-step onboarding, saved back navigation, unavailable adult verification',flush=True)
            for d in drivers:
                errors=[e for e in d.get_log('browser') if any(word in e['message'] for word in ['Uncaught','SyntaxError','violates the following Content Security Policy'])]
                assert not errors,errors
            print('PASS: mobile viewport, navigation and JavaScript console checks',flush=True)
        except BaseException:
            for i,d in enumerate(drivers):
                try:
                    d.save_screenshot(str(ROOT/f'artifacts/failure-{i}.png'))
                    print('BROWSER',i,d.current_url,d.find_element(By.TAG_NAME,'body').text[-3500:],d.get_log('browser'),flush=True)
                except Exception:
                    pass
            log.flush();log.seek(0);print(log.read()[-7000:])
            raise
        finally:
            for d in drivers:
                d.quit()
            if process and process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close()


if __name__=='__main__':
    run()
