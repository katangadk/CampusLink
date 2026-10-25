"""Optional prompts: real mobile editing, retries, privacy and dating/chat."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from PIL import Image
import requests
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from campuslink.seed import PASSWORD, seed

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-prompts-') as temp:
        temp = Path(temp)
        database = temp / 'prompts.sqlite3'
        seed(database)
        Image.new('RGB', (300, 400), '#43283f').save(temp / 'test-photo.png')
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
                raise RuntimeError('Prompt test server did not start.')

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

            def save(driver):
                click(driver, '[data-prompt-action=save]')
                WebDriverWait(driver, 15).until(lambda _: driver.execute_script('return document.querySelector(".prompt-save-status")?.textContent') == 'Answers saved.')

            def activate(driver):
                click(driver, 'a[href="/profile"][data-nav]')
                wait(driver, '#prompt-manager')
                click(driver, '[data-action=dating-settings]')
                click(driver, '#dating-form [name=dating_enabled]')
                click(driver, '#dating-form button[type=submit]')
                wait(driver, '.dating-card')

            def search(driver, name, card='.dating-card'):
                fill(driver, '#student-search', name)
                WebDriverWait(driver, 15).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, card)) == 1 and name in driver.find_element(By.CSS_SELECTOR, card + ' h3').text)

            try:
                start()
                alice, brian = browser(mobile=True), browser()
                login(alice, 'alice')
                assert me(alice)['prompts'] == []
                click(alice, '[data-prompt-action=add]')
                click(alice, '[data-prompt-action=save]')
                text(alice, 'Answer 1 needs 1–280 characters')
                assert me(alice)['prompts'] == []
                fill(alice, '#prompt-answer-0', 'x' * 320)
                assert len(alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value')) == 280
                fill(alice, '#prompt-answer-0', 'Good playlists, books, and the story behind a song.')
                click(alice, '[data-prompt-action=add]')
                fill(alice, '#prompt-answer-1', 'A walk after class and a snack together.')
                click(alice, '[data-prompt-action=add]')
                literal = '<img src=x onerror="window.promptInjected=1"> Books & friends.'
                fill(alice, '#prompt-answer-2', literal)
                assert not alice.find_elements(By.CSS_SELECTOR, '[data-prompt-action=add]')
                Select(alice.find_element(By.ID, 'prompt-question-2')).select_by_value('green_flag')
                assert alice.find_element(By.ID, 'prompt-answer-2').get_attribute('value') == literal
                assert alice.execute_script('return document.activeElement.id') == 'prompt-question-2'
                click(alice, '[data-prompt-index="2"] [data-prompt-action=earlier]')
                assert alice.find_element(By.ID, 'prompt-answer-1').get_attribute('value') == literal
                click(alice, '[data-prompt-index="1"] [data-prompt-action=later]')
                fill(alice, '#profile-form [name=bio]', 'Unsaved profile text survives saving answers.')
                save(alice)
                assert alice.find_element(By.CSS_SELECTOR, '#profile-form [name=bio]').get_attribute('value') == 'Unsaved profile text survives saving answers.'
                assert len(me(alice)['prompts']) == 3
                click(alice, '[data-prompt-index="1"] [data-prompt-action=remove]')
                save(alice)
                assert [item['prompt_id'] for item in me(alice)['prompts']] == ['talk_hours', 'green_flag']
                click(alice, '[data-prompt-action=add]')
                fill(alice, '#prompt-answer-2', 'Coffee and a conversation after class.')
                save(alice)
                assert not alice.execute_script('return document.documentElement.scrollWidth>innerWidth')
                alice.execute_script('document.querySelector("#prompt-manager").scrollIntoView({block:"start"})')
                alice.save_screenshot(str(output / 'prompt-editor-mobile.png'))
                print('PASS: optional mobile prompts, empty/long input, question editing, cap, order and removal; profile draft survives', flush=True)

                fill(alice, '#prompt-answer-0', 'A prompt draft that survives other profile changes.')
                click(alice, '#profile-form button[type=submit]')
                text(alice, 'Profile and preferences saved.')
                assert alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value') == 'A prompt draft that survives other profile changes.'
                assert me(alice)['prompts'][0]['answer'] != 'A prompt draft that survives other profile changes.'
                wait(alice, '#profile-photo-file').send_keys(str(temp / 'test-photo.png'))
                click(alice, '[data-photo-action=upload]')
                WebDriverWait(alice, 15).until(lambda _: len(me(alice)['photos']) == 1)
                assert alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value') == 'A prompt draft that survives other profile changes.'
                save(alice)
                assert len(me(alice)['photos']) == 1
                click(alice, 'a[href="/discover"][data-nav]')
                click(alice, 'a[href="/profile"][data-nav]')
                assert alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value') == 'A prompt draft that survives other profile changes.'
                print('PASS: profile saves, photo uploads and in-tab navigation preserve prompt edits and unrelated data', flush=True)

                fill(alice, '#prompt-answer-0', 'Friday afternoons: music, a walk, and a good conversation.')
                alice.execute_cdp_cmd('Network.enable', {})
                alice.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': True, 'latency': 0, 'downloadThroughput': 0, 'uploadThroughput': 0})
                click(alice, '[data-prompt-action=save]')
                text(alice, 'Retry saving answers')
                assert alice.find_element(By.ID, 'prompt-answer-0').get_attribute('value').startswith('Friday afternoons')
                alice.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
                save(alice)
                persisted = me(alice)['prompts']
                server.kill()
                server.wait(timeout=5)
                start()
                alice.refresh()
                wait(alice, '#prompt-manager')
                assert me(alice)['prompts'] == persisted
                assert len(alice.find_elements(By.CSS_SELECTOR, '.prompt-editor-item')) == 3
                print('PASS: offline retry retains the draft; a server crash and browser reload preserve saved answers and session', flush=True)

                login(brian, 'brian')
                fill(brian, '#profile-form [name=program]', 'Business Administration')
                click(brian, '#profile-form button[type=submit]')
                text(brian, 'Profile and preferences saved.')
                click(brian, 'a[href="/discover"][data-nav]')
                click(brian, '[data-action=discover-mode][data-mode=friend]')
                search(brian, 'Alice', '.student-card')
                assert not brian.find_elements(By.CSS_SELECTOR, '.student-card .profile-prompts')
                click(brian, '.student-card .dating-photo-open')
                WebDriverWait(brian, 15).until(lambda _: len(brian.find_elements(By.CSS_SELECTOR, '#dialog .prompt-answer')) == 3)
                assert literal in brian.find_element(By.CSS_SELECTOR, '#dialog .profile-prompts').text
                assert not brian.find_elements(By.CSS_SELECTOR, '#dialog .profile-prompts img')
                assert brian.execute_script('return window.promptInjected || null') is None
                click(brian, '#dialog [data-action=close-dialog]')
                activate(alice)
                activate(brian)
                search(brian, 'Alice')
                assert not brian.find_elements(By.CSS_SELECTOR, '.dating-card .profile-prompts')
                click(brian, '.dating-card .dating-photo-open')
                WebDriverWait(brian, 15).until(lambda _: len(brian.find_elements(By.CSS_SELECTOR, '#dialog .prompt-answer')) == 3)
                brian.find_element(By.ID, 'dialog').screenshot(str(output / 'prompt-profile-desktop.png'))
                click(brian, '#dialog [data-action=close-dialog]')
                click(brian, '.dating-card [data-action=like]')
                text(brian, 'Like added.')
                search(alice, 'Brian')
                click(alice, '.dating-card [data-action=like]')
                text(alice, 'It’s a match.')
                click(alice, '#dialog [data-action=open-chat]')
                wait(alice, '#message-input')
                click(brian, '[data-action=view-dating-matches]')
                click(brian, '[data-action=open-chat]')
                wait(brian, '#message-input').send_keys('Your music answer caught my eye.')
                print('PASS: compact discovery, photo-open full answers and safe text in Friends and cross-program Dating; genuine mutual match opens chat', flush=True)

                click(alice, 'a[href="/profile"][data-nav]')
                fill(alice, '#prompt-answer-0', 'Music, new books, and meeting someone from another program.')
                save(alice)
                assert brian.find_element(By.ID, 'message-input').get_attribute('value') == 'Your music answer caught my eye.'
                click(brian, '.chat-header [data-action=view-profile]')
                text(brian, 'Music, new books, and meeting someone from another program.')
                click(brian, '#dialog [data-action=close-dialog]')
                click(brian, '#composer button[type=submit]')
                click(alice, 'a[href="/chats"][data-nav]')
                text(alice, 'Your music answer caught my eye.')
                wait(alice, '#message-input').send_keys('Tell me your favourite song!')
                click(alice, '#composer button[type=submit]')
                text(brian, 'Tell me your favourite song!')
                alice_id = me(alice)['id']
                click(brian, '#chat-safety > summary')
                click(brian, '#chat-safety [data-action=confirm-block-dialog]')
                click(brian, '#dialog [data-action=block-student]')
                WebDriverWait(brian, 15).until(lambda _: not brian.find_elements(By.CSS_SELECTOR, '#composer'))
                assert fetch(brian, '/api/profiles/' + alice_id)['status'] == 404
                print('PASS: updated answers preserve the chat draft, messages flow both ways, and blocking denies direct profile access', flush=True)

                click(alice, 'a[href="/profile"][data-nav]')
                for _ in range(3):
                    click(alice, '[data-prompt-index="0"] [data-prompt-action=remove]')
                save(alice)
                alice.refresh()
                wait(alice, '#prompt-manager')
                assert me(alice)['prompts'] == []
                assert not alice.find_elements(By.CSS_SELECTOR, '.prompt-editor-item')
                for driver in drivers:
                    errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ['Uncaught', 'SyntaxError', 'violates the following Content Security Policy'])]
                    assert not errors, errors
                print('PASS: removing all answers persists an optional empty profile; no uncaught JavaScript or CSP errors', flush=True)
            except BaseException:
                for index, driver in enumerate(drivers):
                    try:
                        driver.save_screenshot(str(output / f'prompt-failure-{index}.png'))
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
