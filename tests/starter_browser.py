"""Conversation starters: explicit sending, safe drafts, retries and active dating access."""
import os
from pathlib import Path
import shutil
import socket
import sqlite3
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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from campuslink.seed import PASSWORD, seed

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-starters-') as temp:
        temp = Path(temp)
        database = temp / 'starters.sqlite3'
        seed(database)
        # Start the actual two-account journey without shared interests.
        with sqlite3.connect(database) as setup:
            setup.execute("DELETE FROM user_interests WHERE user_id IN (SELECT id FROM users WHERE username IN ('alice','brian'))")
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
                raise RuntimeError('Starter test server did not start.')

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

            def activate(driver):
                click(driver, '[data-action=dating-settings]')
                click(driver, '#dating-form [name=dating_enabled]')
                click(driver, '#dating-form button[type=submit]')
                WebDriverWait(driver, 15).until(lambda _: not driver.execute_script('return document.querySelector("#dialog").open'))
                wait(driver, '.dating-card')

            def search(driver, name):
                fill(driver, '#student-search', name)
                WebDriverWait(driver, 15).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.dating-card')) == 1 and name in driver.find_element(By.CSS_SELECTOR, '.dating-card h3').text)

            def suggestions(driver):
                toggle = wait(driver, '[data-starter-action=toggle]')
                if toggle.get_attribute('aria-expanded') != 'true':
                    click(driver, '[data-starter-action=toggle]')
                WebDriverWait(driver, 15).until(lambda _: driver.execute_script('return document.querySelector("#conversation-starters")?.getAttribute("aria-busy")==="false" && document.querySelectorAll(".starter-choice").length===3'))

            def history(driver):
                return fetch(driver, f'/api/chats/{rid}/messages')['body']['items']

            def set_offline(driver, offline):
                driver.execute_cdp_cmd('Network.enable', {})
                driver.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': offline, 'latency': 0, 'downloadThroughput': 0 if offline else -1, 'uploadThroughput': 0 if offline else -1})

            def add_music(driver):
                click(driver, 'a[href="/profile"][data-nav]')
                click(driver, '#profile-form label:has(input[name=interests][value=Music])')
                click(driver, '#profile-form button[type=submit]')
                text(driver, 'Profile and preferences saved.')

            try:
                start()
                alice, brian = browser(mobile=True), browser()
                login(alice, 'alice')
                login(brian, 'brian')
                fill(brian, '#profile-form [name=program]', 'Business Administration')
                click(brian, '#profile-form button[type=submit]')
                text(brian, 'Profile and preferences saved.')
                activate(alice)
                activate(brian)
                search(alice, 'Brian')
                click(alice, '.dating-card [data-action=like]')
                text(alice, 'Like added.')
                assert fetch(alice, '/api/chats')['body']['items'] == []
                search(brian, 'Alice')
                click(brian, '.dating-card [data-action=like]')
                text(brian, 'It’s a match.')
                click(brian, '#dialog [data-action=open-chat]')
                suggestions(brian)
                click(alice, '[data-action=view-dating-matches]')
                click(alice, '[data-action=open-chat]')
                suggestions(alice)
                rid = fetch(alice, '/api/chats')['body']['items'][0]['id']
                assert history(alice) == []
                assert all('A campus question' in item.text for item in alice.find_elements(By.CSS_SELECTOR, '.starter-choice'))
                first = alice.find_element(By.CSS_SELECTOR, '.starter-choice span').text
                alice.find_element(By.CSS_SELECTOR, '.starter-choice').send_keys(Keys.ENTER)
                assert wait(alice, '#message-input').get_attribute('value') == first
                assert history(alice) == []
                alice.find_element(By.ID, 'message-input').send_keys(' I would love to hear yours.')
                edited = alice.find_element(By.ID, 'message-input').get_attribute('value')
                click(alice, '[data-starter-index="1"]')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == edited
                text(alice, 'Your draft is safe.')
                assert history(alice) == []
                click(alice, '#composer button[type=submit]')
                text(brian, edited)
                WebDriverWait(alice, 15).until(lambda _: not alice.find_element(By.ID, 'message-input').get_attribute('value'))
                click(brian, '[data-starter-index="1"]')
                response = brian.find_element(By.ID, 'message-input').get_attribute('value') + ' I enjoy a walk after class.'
                fill(brian, '#message-input', response)
                click(brian, '#composer button[type=submit]')
                text(alice, response)
                assert len(history(alice)) == 2
                assert not alice.execute_script('return document.documentElement.scrollWidth>innerWidth')
                assert alice.execute_script('return document.querySelector("#composer button").getBoundingClientRect().bottom <= (visualViewport?.height || innerHeight)'), 'Send is outside the phone viewport.'
                alice.save_screenshot(str(output / 'starters-fallback-mobile.png'))
                print('PASS: real cross-program mutual matching, no-overlap fallback, keyboard selection, editable drafts, explicit sending and bidirectional messages', flush=True)

                fill(alice, '#message-input', 'A draft that must survive fresh suggestions.')
                add_music(alice)
                add_music(brian)
                click(brian, '[data-prompt-action=add]')
                literal = 'OLD_VISIBLE_ANSWER <img src=x onerror="window.starterInjected=1">'
                fill(brian, '#prompt-answer-0', literal)
                click(brian, '[data-prompt-action=save]')
                WebDriverWait(brian, 15).until(lambda _: brian.execute_script('return document.querySelector(".prompt-save-status")?.textContent') == 'Answers saved.')
                click(alice, 'a[href="/chats"][data-nav]')
                suggestions(alice)
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == 'A draft that must survive fresh suggestions.'
                text(alice, 'You both enjoy Music')
                text(alice, 'OLD_VISIBLE_ANSWER')
                assert not alice.find_elements(By.CSS_SELECTOR, '#conversation-starters img')
                assert alice.execute_script('return window.starterInjected || null') is None
                fill(alice, '#message-input', '')
                click(alice, '[data-starter-index="1"]')
                old_draft = alice.find_element(By.ID, 'message-input').get_attribute('value')
                assert 'OLD_VISIBLE_ANSWER' in old_draft
                fill(brian, '#prompt-answer-0', 'NEW_VISIBLE_ANSWER: music, stories, and good books.')
                click(brian, '[data-prompt-action=save]')
                text(alice, 'NEW_VISIBLE_ANSWER')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == old_draft
                assert len(history(alice)) == 2
                alice.save_screenshot(str(output / 'starters-profile-mobile.png'))
                print('PASS: shared-interest and visible-answer suggestions, safe text rendering, fresh profile updates and preserved existing drafts', flush=True)

                fill(alice, '#message-input', '')
                click(alice, '[data-starter-index="1"]')
                alice.find_element(By.ID, 'message-input').send_keys(' What would you recommend?')
                retry_text = alice.find_element(By.ID, 'message-input').get_attribute('value')
                set_offline(alice, True)
                click(alice, '#composer button[type=submit]')
                wait(alice, '[data-action=retry-message]')
                click(alice, '[data-starter-index="0"]')
                text(alice, 'Retry your unsent message before choosing another starter.')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == retry_text
                set_offline(alice, False)
                click(alice, '[data-action=retry-message]')
                WebDriverWait(alice, 15).until(lambda _: not alice.find_elements(By.CSS_SELECTOR, '[data-action=retry-message]'))
                messages = history(alice)
                assert len(messages) == 3 and sum(item['body'] == retry_text for item in messages) == 1
                click(brian, 'a[href="/chats"][data-nav]')
                text(brian, retry_text)
                print('PASS: failed-send retry preserves the edited starter and sends exactly once; suggestion clicks cannot replace the pending message', flush=True)

                click(alice, '[data-starter-action=toggle]')
                assert alice.find_element(By.CSS_SELECTOR, '[data-starter-action=toggle]').get_attribute('aria-expanded') == 'false'
                click(alice, 'a[href="/profile"][data-nav]')
                click(alice, 'a[href="/chats"][data-nav]')
                wait(alice, '[data-starter-action=toggle]')
                assert alice.find_element(By.CSS_SELECTOR, '[data-starter-action=toggle]').get_attribute('aria-expanded') == 'false'
                fill(alice, '#message-input', 'My own draft while suggestions are unavailable.')
                set_offline(alice, True)
                click(alice, '[data-starter-action=toggle]')
                wait(alice, '[data-starter-action=retry]')
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == 'My own draft while suggestions are unavailable.'
                assert alice.find_element(By.CSS_SELECTOR, '#composer button').is_enabled()
                set_offline(alice, False)
                click(alice, '[data-starter-action=retry]')
                suggestions(alice)
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == 'My own draft while suggestions are unavailable.'
                fill(alice, '#message-input', '')
                assert len(history(alice)) == 3
                print('PASS: hiding is remembered in the tab; suggestions can fail and retry independently without blocking the composer or discarding its draft', flush=True)

                server.kill()
                server.wait(timeout=5)
                start()
                alice.refresh()
                click(alice, '.conversation-item')
                suggestions(alice)
                assert alice.find_element(By.ID, 'message-input').get_attribute('value') == ''
                assert len(history(alice)) == 3
                assert 'NEW_VISIBLE_ANSWER' in alice.find_element(By.ID, 'conversation-starters').text
                click(alice, '#chat-safety > summary')
                click(alice, '#chat-safety [data-action=confirm-block-dialog]')
                click(alice, '#dialog [data-action=block-student]')
                for driver in (alice, brian):
                    WebDriverWait(driver, 15).until(lambda _, d=driver: not d.find_elements(By.CSS_SELECTOR, '#composer'))
                    assert not driver.find_elements(By.CSS_SELECTOR, '.starter-choice')
                    assert fetch(driver, f'/api/chats/{rid}/starters')['status'] in (403, 404)
                for driver in drivers:
                    errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ['Uncaught', 'SyntaxError', 'violates the following Content Security Policy'])]
                    assert not errors, errors
                print('PASS: restart restores saved messages and fresh suggestions without pre-filling or sending; blocking revokes UI/API access; no uncaught JavaScript or CSP errors', flush=True)
            except BaseException:
                for index, driver in enumerate(drivers):
                    try:
                        driver.save_screenshot(str(output / f'starter-failure-{index}.png'))
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
