"""End-to-end Dating: activation, privacy, match/chat, unmatch, disable and demo access.

Run with local Chromium/chromedriver: python3 -m tests.dating_browser
All records are isolated fictional fixtures in a temporary database.
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
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select

from campuslink.seed import PASSWORD, seed

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-dating-') as temp:
        database = Path(temp) / 'dating.sqlite3'
        seed(database)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'CAMPUSLINK_DB': str(database), 'CAMPUSLINK_MODE': 'local'}
        drivers = []
        artifacts = ROOT / 'artifacts'
        artifacts.mkdir(exist_ok=True)
        with open(Path(temp) / 'server.log', 'w+') as log:
            server = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'campuslink.app:app', '--host', '127.0.0.1',
                 '--port', str(port), '--timeout-graceful-shutdown', '2'],
                cwd=ROOT, env=env, stdout=log, stderr=log,
            )

            def browser(mobile=False):
                options = Options()
                options.binary_location = shutil.which('chromium') or shutil.which('google-chrome')
                for flag in ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server',
                             '--window-size=390,900' if mobile else '--window-size=1280,1000']:
                    options.add_argument(flag)
                options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
                driver = webdriver.Chrome(service=Service(shutil.which('chromedriver')), options=options)
                if mobile:
                    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                        'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True,
                    })
                drivers.append(driver)
                return driver

            def wait(driver, selector):
                return WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

            def click(driver, selector):
                def attempt(_):
                    element = EC.element_to_be_clickable((By.CSS_SELECTOR, selector))(driver)
                    if not element:
                        return False
                    driver.execute_script('arguments[0].scrollIntoView({block:"center"})', element)
                    element.click()
                    return True
                WebDriverWait(driver, 15, ignored_exceptions=(StaleElementReferenceException,)).until(attempt)

            def text(driver, expected):
                WebDriverWait(driver, 15).until(lambda _: expected in driver.find_element(By.TAG_NAME, 'body').text)

            def login(driver, name):
                driver.get(url + '/login')
                wait(driver, '[name=email]').send_keys(name + '@campuslink.test')
                driver.find_element(By.NAME, 'password').send_keys(PASSWORD)
                click(driver, '#auth-form button[type=submit]')
                wait(driver, '.dating-welcome')
                assert wait(driver, '[data-mode=dating]').get_attribute('aria-selected') == 'true'

            def activate(driver):
                click(driver, '[data-action=dating-settings]')
                checkbox = wait(driver, '#dating-form [name=dating_enabled]')
                assert not checkbox.is_selected()
                click(driver, '#dating-form [name=dating_enabled]')
                click(driver, '#dating-form button[type=submit]')
                wait(driver, '.dating-card')

            def search(driver, name):
                field = wait(driver, '#student-search')
                field.clear()
                field.send_keys(name)
                WebDriverWait(driver, 15).until(
                    lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.dating-card')) == 1
                    and name.casefold() in driver.find_element(By.CSS_SELECTOR, '.dating-card h3').text.casefold()
                )

            def fetch(driver, endpoint):
                return driver.execute_async_script(
                    'const done=arguments[arguments.length-1];fetch(arguments[0]).then(async r=>done({status:r.status,body:await r.json()})).catch(e=>done({error:String(e)}));',
                    '/api' + endpoint,
                )

            def send(driver, body):
                wait(driver, '#message-input').send_keys(body)
                click(driver, '#composer button[type=submit]')
                WebDriverWait(driver, 15).until(lambda _: not driver.find_element(By.ID, 'message-input').get_attribute('value'))

            try:
                for _ in range(100):
                    try:
                        if requests.get(url + '/api/health', timeout=.5).ok:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('Dating test server did not start.')

                alice, brian = browser(mobile=True), browser()
                login(alice, 'alice')
                assert alice.execute_script('return innerWidth') == 390
                assert alice.execute_script('return document.querySelector(".dating-welcome [data-action=dating-settings]").getBoundingClientRect().bottom < innerHeight - 68')
                assert fetch(alice, '/me')['body']['user']['dating_enabled'] == 0
                alice.save_screenshot(str(artifacts / 'dating-setup-mobile.png'))
                activate(alice)
                assert len(alice.find_elements(By.CSS_SELECTOR, '.dating-card')) >= 2
                assert not alice.execute_script('return document.documentElement.scrollWidth > innerWidth')
                alice.save_screenshot(str(artifacts / 'dating-discovery-mobile.png'))
                search(alice, 'Daniel')
                click(alice, '.dating-card [data-action=student-menu]')
                click(alice, '#dialog [data-action=dismiss]')
                text(alice, 'No more profiles for now.')
                click(alice, '#discovery-results [data-action=clear-filters]')
                wait(alice, '.dating-card')
                assert 'Daniel Lungu' not in alice.find_element(By.ID, 'discovery-results').text
                print('PASS: Dating is visible first; explicit mobile setup, eligible fixtures, Pass and cooldown work', flush=True)

                login(brian, 'brian')
                activate(brian)
                before = fetch(brian, '/notifications')['body']['items']
                search(alice, 'Brian')
                click(alice, '.dating-card [data-action=like]')
                text(alice, 'No more profiles for now.')
                assert not alice.find_elements(By.CSS_SELECTOR, '#dialog[open]')
                assert fetch(brian, '/notifications')['body']['items'] == before
                assert fetch(brian, '/connections')['body']['items'] == []
                search(brian, 'Alice')
                click(brian, '.dating-card [data-action=like]')
                text(brian, 'It’s a match.')
                brian.save_screenshot(str(artifacts / 'dating-mutual-match.png'))
                click(brian, '#dialog [data-action=open-chat]')
                wait(brian, '#message-input')
                send(brian, 'Hi Alice, happy we matched!')
                click(alice, '[data-action=view-dating-matches]')
                text(alice, 'Brian Mwansa')
                click(alice, '[data-action=open-chat]')
                text(alice, 'Hi Alice, happy we matched!')
                send(alice, 'Hi Brian! What music are you into?')
                text(brian, 'Hi Brian! What music are you into?')
                relationships = fetch(alice, '/connections')['body']['items']
                assert len(relationships) == 1 and relationships[0]['kind'] == 'dating'
                relationship_id = relationships[0]['id']
                alice.save_screenshot(str(artifacts / 'dating-chat-mobile.png'))
                print('PASS: one-sided likes stay outside chat; mutual matching opens real bidirectional dating chat without a friendship', flush=True)

                # Unmatching closes both clients and requires fresh mutual likes.
                click(brian, 'a[href="/matches"][data-nav]')
                click(brian, '[data-action=remove-connection]')
                click(brian, '#dialog [data-action=confirm-remove]')
                WebDriverWait(alice, 15).until(lambda _: not alice.find_elements(By.CSS_SELECTOR, '#composer'))
                assert fetch(alice, f'/chats/{relationship_id}/messages')['status'] == 403
                print('PASS: Unmatch revokes live and direct history access', flush=True)

                for driver, target in [(alice, 'Brian'), (brian, 'Alice')]:
                    driver.get(url + '/dating')
                    wait(driver, '.dating-card')
                    search(driver, target)
                    click(driver, '.dating-card [data-action=like]')
                text(brian, 'It’s a match.')
                click(brian, '#dialog [data-action=open-chat]')
                wait(brian, '#message-input')
                alice.get(url + '/dating')
                click(alice, '[data-action=dating-settings]')
                click(alice, '#dating-form [name=dating_enabled]')
                click(alice, '#dating-form button[type=submit]')
                wait(alice, '.dating-welcome')
                WebDriverWait(brian, 15).until(lambda _: not brian.find_elements(By.CSS_SELECTOR, '#composer'))
                assert fetch(alice, '/connections')['body']['items'] == []
                print('PASS: disabling Dating ends existing matches and the other browser loses chat access', flush=True)

                # New accounts have a visible, usable adult-fixture demo path.
                newcomer = requests.Session()
                registered = newcomer.post(url + '/api/auth/register', json={
                    'email': 'dating_browser@campuslink.test', 'username': 'dating_browser',
                    'display_name': 'Dating Browser', 'password': PASSWORD, 'agreement': True,
                })
                registered.raise_for_status()
                newcomer.headers['X-CSRF-Token'] = registered.json()['csrf']
                completed = newcomer.patch(url + '/api/me', json={'program': 'Computer Science', 'onboarding_step': 6})
                completed.raise_for_status()
                brian.delete_all_cookies()
                brian.add_cookie({'name': 'campuslink_session', 'value': newcomer.cookies['campuslink_session'], 'path': '/'})
                brian.get(url + '/dating')
                wait(brian, '.dating-welcome')
                click(brian, '.dating-welcome [data-action=dating-settings]')
                click(brian, '[data-action=dating-test-accounts]')
                click(brian, '[data-action=switch-dating-test][data-account=alice]')
                text(brian, 'Adult test account opened. Choose Set up Dating to opt in.')
                wait(brian, '.dating-welcome [data-action=dating-settings]')
                current = fetch(brian, '/me')['body']['user']
                assert current['username'] == 'alice' and current['dating_enabled'] == 0
                assert current['verified'] is False
                assert newcomer.get(url + '/api/me').status_code == 401
                print('PASS: a new account can explicitly switch to an adult demo; activation remains optional and old session is revoked', flush=True)

                # The user's actual test case: Alice and a newly created account.
                own_login = newcomer.post(url + '/api/auth/login', json={'email':'dating_browser@campuslink.test','password':PASSWORD})
                own_login.raise_for_status()
                brian.delete_all_cookies()
                brian.add_cookie({'name':'campuslink_session','value':newcomer.cookies['campuslink_session'],'path':'/'})
                brian.get(url + '/dating')
                click(brian, '.dating-welcome [data-action=dating-settings]')
                wait(brian, '#dating-eligibility-form [name=dob]')
                brian.execute_script('document.querySelector("#dating-eligibility-form [name=dob]").value="2015-06-15"')
                click(brian, '#dating-eligibility-form [name=adult_test_agreement]')
                click(brian, '#dating-eligibility-form button[type=submit]')
                text(brian, 'Dating test access is restricted to people aged 18 or older.')
                brian.execute_script('document.querySelector("#dating-eligibility-form [name=dob]").value="2001-06-15"')
                click(brian, '#dating-eligibility-form button[type=submit]')
                wait(brian, '#dating-form')
                assert fetch(brian, '/me')['body']['user']['dating_enabled']==0
                Select(brian.find_element(By.CSS_SELECTOR, '#dating-form [name=gender]')).select_by_value('man')
                click(brian, '#dating-form [name=dating_genders][value=woman]')
                click(brian, '#dating-form [name=dating_enabled]')
                click(brian, '#dating-form button[type=submit]')
                wait(brian, '.dating-card')
                assert fetch(brian, '/me')['body']['user']['verified'] is False
                activate(alice)
                search(alice, 'Dating Browser')
                click(alice, '.dating-card [data-action=like]')
                search(brian, 'Alice')
                click(brian, '.dating-card [data-action=like]')
                text(brian, 'It’s a match.')
                click(brian, '#dialog [data-action=open-chat]')
                send(brian, 'A real match between Alice and my created test account.')
                click(alice, '[data-action=view-dating-matches]')
                text(alice, 'Dating Browser')
                click(alice, '[data-action=open-chat]')
                text(alice, 'A real match between Alice and my created test account.')
                print('PASS: created account rejects under-18 access, declares local adult test access, opts in, matches Alice and exchanges a real message', flush=True)

                for driver in drivers:
                    errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ['Uncaught', 'SyntaxError', 'violates the following Content Security Policy'])]
                    assert not errors, errors
                print('PASS: no uncaught JavaScript errors or CSP violations in the Dating journey', flush=True)
            except BaseException:
                for index, driver in enumerate(drivers):
                    try:
                        driver.save_screenshot(str(artifacts / f'dating-failure-{index}.png'))
                        print('BROWSER', index, driver.current_url, driver.find_element(By.TAG_NAME, 'body').text[-4000:], driver.get_log('browser'), flush=True)
                    except Exception:
                        pass
                log.flush()
                log.seek(0)
                print(log.read()[-5000:])
                raise
            finally:
                for driver in drivers:
                    driver.quit()
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    run()
