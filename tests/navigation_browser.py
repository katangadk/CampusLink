"""Dating-first navigation: real connections, routing, profile shortcuts and recovery."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import requests
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from campuslink.seed import PASSWORD, seed

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-navigation-') as temp:
        temp = Path(temp)
        database = temp / 'navigation.sqlite3'
        seed(database)
        Image.new('RGB', (400, 500), '#43283f').save(temp / 'navigation-photo.png')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'CAMPUSLINK_DB': str(database), 'CAMPUSLINK_MODE': 'local'}
        drivers, server = [], None
        output = ROOT / 'artifacts'
        output.mkdir(exist_ok=True)
        with open(temp / 'server.log', 'w+') as log:
            def start():
                nonlocal server
                server = subprocess.Popen([os.getenv('CAMPUSLINK_TEST_PYTHON', sys.executable), '-m', 'uvicorn', 'campuslink.app:app', '--host', '127.0.0.1', '--port', str(port), '--timeout-graceful-shutdown', '2', '--log-level', 'warning'], cwd=ROOT, env=env, stdout=log, stderr=log)
                for _ in range(100):
                    try:
                        if requests.get(url + '/api/health', timeout=.5).ok:
                            return
                    except requests.RequestException:
                        pass
                    time.sleep(.1)
                raise RuntimeError('Navigation test server did not start.')

            def browser(mobile=False):
                options = Options()
                options.binary_location = shutil.which('chromium') or shutil.which('google-chrome')
                for flag in ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server', '--window-size=1280,1000']:
                    options.add_argument(flag)
                options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
                driver = webdriver.Chrome(service=Service(shutil.which('chromedriver')), options=options)
                if mobile:
                    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
                drivers.append(driver)
                return driver

            def wait(driver, selector):
                return WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

            def click(driver, selector):
                def attempt(_):
                    button = EC.element_to_be_clickable((By.CSS_SELECTOR, selector))(driver)
                    if not button:
                        return False
                    driver.execute_script('arguments[0].scrollIntoView({block:"center"})', button)
                    button.click()
                    return True
                WebDriverWait(driver, 15, ignored_exceptions=(StaleElementReferenceException,)).until(attempt)

            def text(driver, expected):
                WebDriverWait(driver, 15).until(lambda _: expected in driver.find_element(By.TAG_NAME, 'body').text)

            def fetch(driver, endpoint):
                return driver.execute_async_script('const done=arguments[arguments.length-1];fetch(arguments[0]).then(async r=>done({status:r.status,body:await r.json()})).catch(e=>done({error:String(e)}));', endpoint)

            def me(driver):
                return fetch(driver, '/api/me')['body']['user']

            def login(driver, name):
                driver.get(url + '/login')
                wait(driver, '[name=email]').send_keys(name + '@campuslink.test')
                driver.find_element(By.NAME, 'password').send_keys(PASSWORD)
                click(driver, '#auth-form button[type=submit]')
                wait(driver, '.dating-welcome')
                click(driver, 'a[href="/profile"][data-nav]')
                wait(driver, '#prompt-manager')

            def fill(driver, selector, value):
                field = wait(driver, selector)
                field.clear()
                field.send_keys(value)

            def main_nav(driver, destination):
                click(driver, f'.nav a[href="/{destination}"]')

            def route(driver, pathname, query=None):
                WebDriverWait(driver, 15).until(lambda _: driver.execute_script('return location.pathname') == pathname and (query is None or driver.execute_script('return location.search') == query))

            def assert_main_nav(driver, current):
                assert [link.find_element(By.TAG_NAME, 'span').text for link in driver.find_elements(By.CSS_SELECTOR, '.nav a')] == ['Feed', 'Discover', 'Matches', 'Inbox', 'Profile']
                assert [link.get_attribute('href').rsplit('/', 1)[-1] for link in driver.find_elements(By.CSS_SELECTOR, '.nav a[aria-current=page]')] == [current]
                assert driver.execute_script('return [...document.querySelectorAll(".nav a")].every(a=>a.getBoundingClientRect().height>=44 && a.getBoundingClientRect().width>=44)')

            def search(driver, name):
                fill(driver, '#student-search', name)
                WebDriverWait(driver, 15).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.student-card')) == 1 and name in driver.find_element(By.CSS_SELECTOR, '.student-card h3').text)

            def activate(driver):
                main_nav(driver, 'profile')
                click(driver, '.profile-edit-nav [data-action=dating-settings]')
                click(driver, '#dating-form [name=dating_enabled]')
                click(driver, '#dating-form button[type=submit]')
                wait(driver, '.dating-card')

            def block(driver, suffixes):
                driver.execute_cdp_cmd('Network.enable', {})
                driver.execute_cdp_cmd('Network.setBlockedURLs', {'urls': [url + suffix for suffix in suffixes]})

            def jump(driver, section):
                click(driver, f'.profile-edit-nav a[href="#{section}"]')
                assert driver.execute_script('return document.activeElement.id') == section
                assert driver.execute_script('return location.hash') == '#' + section

            def contrast(driver, selector):
                return driver.execute_script(r'''
const element=document.querySelector(arguments[0]);
function rgb(value){return value.match(/[\d.]+/g).slice(0,3).map(Number);}
function lum(values){return values.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
let bg=element;
while(bg.parentElement && ['transparent','rgba(0, 0, 0, 0)'].includes(getComputedStyle(bg).backgroundColor))bg=bg.parentElement;
const a=lum(rgb(getComputedStyle(element).color)),b=lum(rgb(getComputedStyle(bg).backgroundColor));
return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
''', selector)

            try:
                start()
                alice, brian = browser(mobile=True), browser()
                login(alice, 'alice')
                login(brian, 'brian')
                assert_main_nav(alice, 'profile')
                alice.find_element(By.CSS_SELECTOR, '.nav a[href="/matches"]').send_keys(Keys.ENTER)
                route(alice, '/matches')
                text(alice, 'Your matches start here.')
                assert_main_nav(alice, 'matches')
                assert alice.execute_script('return document.activeElement.id') == 'main'
                main_nav(alice, 'discover')
                wait(alice, '.dating-welcome')
                tab = alice.find_element(By.ID, 'discovery-tab-dating')
                tab.send_keys(Keys.ARROW_RIGHT)
                route(alice, '/discover', '?mode=for-you')
                assert alice.execute_script('return document.activeElement.id') == 'discovery-tab-for-you'
                alice.find_element(By.ID, 'discovery-tab-for-you').send_keys(Keys.ARROW_RIGHT)
                route(alice, '/discover', '?mode=friend')
                search(alice, 'Brian')
                click(alice, '[data-action=connect][data-kind=friend]')
                text(alice, 'Request sent.')
                main_nav(alice, 'matches')
                assert not alice.find_elements(By.CSS_SELECTOR, '.connection-card')
                click(alice, '.connection-areas a[href="/connections"]')
                click(alice, '[data-action=connection-filter][data-filter=sent]')
                route(alice, '/connections', '?view=sent')
                text(alice, 'Brian Mwansa')
                alice.find_element(By.ID, 'connection-tab-sent').send_keys(Keys.ARROW_RIGHT)
                route(alice, '/connections', '?view=friend')
                assert alice.execute_script('return document.activeElement.id') == 'connection-tab-friend'
                alice.back()
                route(alice, '/connections', '?view=sent')
                text(alice, 'Brian Mwansa')
                assert alice.execute_script('return document.activeElement.id') == 'main'
                alice.forward()
                route(alice, '/connections', '?view=friend')
                click(alice, '[data-action=connection-filter][data-filter=study]')
                route(alice, '/connections', '?view=study')
                text(alice, 'Find your next study partner.')
                click(alice, '#connection-results a[href="/discover?mode=study"]')
                route(alice, '/discover', '?mode=study')
                assert alice.find_element(By.ID, 'discovery-tab-study').get_attribute('aria-selected') == 'true'
                main_nav(alice, 'matches')
                route(alice, '/matches', '')
                assert not alice.find_elements(By.CSS_SELECTOR, '.connection-card')
                print('PASS: five main destinations, Dating defaults, keyboard tabs/focus, URL-backed secondary views and Back/Forward routing', flush=True)

                main_nav(brian, 'matches')
                text(brian, 'Your matches start here.')
                WebDriverWait(brian, 15).until(lambda _: brian.find_element(By.CSS_SELECTOR, '.connection-areas [data-badge=requests]').text == '1')
                assert not brian.find_elements(By.CSS_SELECTOR, '.connection-card')
                assert '1 pending request' in brian.find_element(By.CSS_SELECTOR, '.connection-areas a[data-request-link]').get_attribute('aria-label')
                click(brian, '.connection-areas a[href="/connections"]')
                click(brian, '[data-command=accept]')
                text(brian, 'No requests just yet.')
                click(brian, '[data-action=connection-filter][data-filter=friend]')
                text(brian, 'Alice Banda')
                main_nav(brian, 'matches')
                assert not brian.find_elements(By.CSS_SELECTOR, '.connection-card')
                activate(alice)
                activate(brian)
                search(alice, 'Brian')
                click(alice, '.dating-card [data-action=like]')
                text(alice, 'Like added.')
                main_nav(alice, 'matches')
                assert not alice.find_elements(By.CSS_SELECTOR, '.connection-card')
                search(brian, 'Alice')
                click(brian, '.dating-card [data-action=like]')
                text(brian, 'It’s a match.')
                click(brian, '#dialog [data-action=close-dialog]')
                for driver, name in [(alice, 'Brian'), (brian, 'Alice')]:
                    main_nav(driver, 'matches')
                    WebDriverWait(driver, 15).until(lambda _, d=driver: len(d.find_elements(By.CSS_SELECTOR, '.connection-card')) == 1)
                    assert 'Dating' in driver.find_element(By.CSS_SELECTOR, '.connection-card .pill').text
                    assert not driver.find_elements(By.CSS_SELECTOR, '[data-action=connection-filter]')
                    click(driver, '.connection-card [data-action=open-chat]')
                    wait(driver, '#message-input')
                    assert driver.find_element(By.CSS_SELECTOR, '.chat-header').get_attribute('data-chat-kind') == 'dating'
                wait(alice, '#message-input').send_keys('Hello through the new Matches navigation!')
                click(alice, '#composer button[type=submit]')
                text(brian, 'Hello through the new Matches navigation!')
                wait(brian, '#message-input').send_keys('I found our match straight away.')
                click(brian, '#composer button[type=submit]')
                text(alice, 'I found our match straight away.')
                main_nav(alice, 'matches')
                alice.save_screenshot(str(output / 'matches-navigation-mobile.png'))
                print('PASS: friendship requests stay secondary, request badges are clear, a one-sided public like does not open a chat, and mutual Matches opens real bidirectional dating chat', flush=True)

                main_nav(alice, 'profile')
                fill(alice, '#profile-form [name=bio]', 'BIO_DRAFT saved through the new profile shortcuts.')
                click(alice, '[data-prompt-action=add]')
                fill(alice, '#prompt-answer-0', 'PROMPT_DRAFT kept while jumping between editors.')
                jump(alice, 'photo-manager')
                wait(alice, '#profile-photo-file').send_keys(str(temp / 'navigation-photo.png'))
                click(alice, '[data-photo-action=upload]')
                WebDriverWait(alice, 15).until(lambda _: len(alice.find_elements(By.CSS_SELECTOR, '.photo-tile')) == 1)
                assert alice.find_element(By.CSS_SELECTOR, '#profile-form [name=bio]').get_attribute('value').startswith('BIO_DRAFT')
                jump(alice, 'prompt-manager')
                assert alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value').startswith('PROMPT_DRAFT')
                jump(alice, 'profile-visibility')
                click(alice, '#profile-form [name=discoverable]')
                click(alice, '#profile-form button[type=submit]')
                text(alice, 'Profile and preferences saved.')
                assert me(alice)['discoverable'] == 0
                assert alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value').startswith('PROMPT_DRAFT')
                jump(alice, 'prompt-manager')
                click(alice, '[data-prompt-action=save]')
                WebDriverWait(alice, 15).until(lambda _: alice.execute_script('return document.querySelector(".prompt-save-status")?.textContent') == 'Answers saved.')
                click(alice, '.profile-edit-nav [data-action=dating-settings]')
                wait(alice, '#dating-form [name=dating_intention]')
                alice.find_element(By.CSS_SELECTOR, '#dialog [data-action=close-dialog]').send_keys(Keys.ESCAPE)
                WebDriverWait(alice, 15).until(lambda _: not alice.execute_script('return document.querySelector("#dialog").open'))
                assert alice.execute_script('return document.activeElement.dataset.action') == 'dating-settings'
                alice.refresh()
                wait(alice, '#prompt-manager')
                assert alice.execute_script('return document.activeElement.id') == 'prompt-manager'
                assert me(alice)['bio'].startswith('BIO_DRAFT') and len(me(alice)['photos']) == 1
                assert me(alice)['prompts'][0]['answer'].startswith('PROMPT_DRAFT')
                alice.save_screenshot(str(output / 'profile-shortcuts-mobile.png'))
                print('PASS: photo/prompt/preference/visibility shortcuts preserve drafts, save real data and support direct hash links and dialog focus restoration', flush=True)

                block(alice, ['/api/connections*'])
                alice.get(url + '/matches')
                text(alice, 'Couldn’t load matches.')
                assert 'No matches yet.' not in alice.find_element(By.ID, 'connection-results').text
                main_nav(alice, 'chats')
                WebDriverWait(alice, 15).until(lambda _: len(alice.find_elements(By.CSS_SELECTOR, '.conversation-item')) == 2)
                main_nav(alice, 'matches')
                text(alice, 'Couldn’t load matches.')
                block(alice, [])
                click(alice, '[data-action=retry-data]')
                WebDriverWait(alice, 15).until(lambda _: len(alice.find_elements(By.CSS_SELECTOR, '.connection-card')) == 1)
                block(alice, ['/api/connections*'])
                click(alice, '[data-action=retry-data]')
                wait(alice, '.refresh-error[role=alert]')
                assert len(alice.find_elements(By.CSS_SELECTOR, '.connection-card')) == 1
                block(alice, [])
                click(alice, '[data-action=retry-data]')
                WebDriverWait(alice, 15).until(lambda _: not alice.find_elements(By.CSS_SELECTOR, '.refresh-error'))
                block(alice, ['/api/chats'])
                alice.get(url + '/chats')
                text(alice, 'Couldn’t load your chats.')
                block(alice, [])
                click(alice, '[data-action=retry-data]')
                WebDriverWait(alice, 15).until(lambda _: len(alice.find_elements(By.CSS_SELECTOR, '.conversation-item')) == 2)
                click(alice, '[data-action=chat-filter][data-filter=dating]')
                click(alice, '.conversation-item')
                text(alice, 'Hello through the new Matches navigation!')
                fill(alice, '#message-input', 'A draft safe through message-history retry.')
                block(alice, ['/api/chats/*/messages*'])
                main_nav(alice, 'profile')
                main_nav(alice, 'chats')
                wait(alice, '[data-action=retry-conversation]')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == 'A draft safe through message-history retry.'
                block(alice, [])
                click(alice, '[data-action=retry-conversation]')
                text(alice, 'Hello through the new Matches navigation!')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == 'A draft safe through message-history retry.'
                assert alice.find_element(By.ID, 'composer').is_displayed()
                wait(alice, '[data-starter-action=toggle]')
                block(alice, ['/api/chats/*/messages*'])
                main_nav(alice, 'profile')
                main_nav(alice, 'chats')
                wait(alice, '[data-action=retry-conversation]')
                block(alice, [])
                alice.execute_script('window.dispatchEvent(new Event("online"))')
                WebDriverWait(alice, 15).until(lambda _: alice.find_element(By.ID, 'composer').is_displayed())
                wait(alice, '[data-starter-action=toggle]')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == 'A draft safe through message-history retry.'
                block(alice, ['/api/discover*'])
                main_nav(alice, 'discover')
                text(alice, 'Discovery is unavailable.')
                block(alice, [])
                click(alice, '[data-action=retry-discovery]')
                wait(alice, '.dating-card')
                print('PASS: independent list failures, truthful error states, cached-list warnings, message-history draft recovery and discovery retries', flush=True)

                alice.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': False, 'latency': 500, 'downloadThroughput': -1, 'uploadThroughput': -1})
                alice.get(url + '/matches')
                wait(alice, '.initial-loading [role=status]')
                wait(alice, '.connection-card')
                alice.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
                assert_main_nav(alice, 'matches')
                assert contrast(alice, '.nav a[aria-current=page]') >= 4.5
                assert contrast(alice, '.connection-areas a[aria-current=page]') >= 4.5
                assert contrast(alice, '.page-heading p') >= 4.5
                alice.find_element(By.ID, 'main').send_keys(Keys.TAB)
                assert alice.execute_script('return parseFloat(getComputedStyle(document.activeElement).outlineWidth)') >= 3
                assert not alice.execute_script('return document.documentElement.scrollWidth>innerWidth')
                assert alice.execute_script('return [...document.querySelectorAll(".nav a")].every(a=>a.getBoundingClientRect().bottom<=innerHeight)')
                for driver in drivers:
                    errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ['Uncaught', 'SyntaxError', 'violates the following Content Security Policy'])]
                    assert not errors, errors
                print('PASS: loading feedback, readable contrast, visible keyboard focus, phone touch targets/layout and no uncaught JavaScript or CSP errors', flush=True)
            except BaseException:
                for index, driver in enumerate(drivers):
                    try:
                        driver.save_screenshot(str(output / f'navigation-failure-{index}.png'))
                        print('BROWSER', index, driver.current_url, driver.find_element(By.TAG_NAME, 'body').text[-3500:], driver.get_log('browser'), flush=True)
                    except Exception:
                        pass
                log.flush()
                log.seek(0)
                print(log.read()[-4000:])
                raise
            finally:
                for driver in drivers:
                    driver.quit()
                if server and server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()


if __name__ == '__main__':
    run()
