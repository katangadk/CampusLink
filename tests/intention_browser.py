"""Dating intentions: mobile settings, private filters, contextual profiles and chat."""
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
from selenium.webdriver.support.ui import Select, WebDriverWait

from campuslink.seed import PASSWORD, seed

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-intentions-') as temp:
        temp = Path(temp)
        database = temp / 'intentions.sqlite3'
        seed(database)
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
                raise RuntimeError('Intention test server did not start.')

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

            def settings(driver):
                click(driver, 'a[href="/profile"][data-nav]')
                click(driver, '[data-action=dating-settings]')
                wait(driver, '#dating-form [name=dating_intention]')

            def choice(driver, value, displayed=False):
                Select(wait(driver, '#dating-form [name=dating_intention]')).select_by_value(value)
                checkbox = driver.find_element(By.CSS_SELECTOR, '#dating-form [name=show_dating_intention]')
                if checkbox.is_selected() != displayed:
                    click(driver, '#dating-form [name=show_dating_intention]')

            def submit(driver):
                click(driver, '#dating-form button[type=submit]')
                WebDriverWait(driver, 15).until(lambda _: not driver.execute_script('return document.querySelector("#dialog").open'))
                wait(driver, '#discovery-results')

            def activate(driver, value='', displayed=False):
                settings(driver)
                assert not driver.find_element(By.NAME, 'show_dating_intention').is_enabled()
                assert not driver.find_element(By.NAME, 'show_dating_intention').is_selected()
                Select(wait(driver, '#dating-form [name=dating_intention]')).select_by_value(value)
                assert not driver.find_element(By.NAME, 'show_dating_intention').is_selected()
                choice(driver, value, displayed)
                click(driver, '#dating-form [name=dating_enabled]')
                submit(driver)

            def search(driver, name):
                fill(driver, '#student-search', name)
                WebDriverWait(driver, 15).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.student-card')) == 1 and name in driver.find_element(By.CSS_SELECTOR, '.student-card h3').text)

            def filter_intention(driver, value):
                if 'hidden' in driver.find_element(By.ID, 'search-filters').get_attribute('class'):
                    click(driver, '[data-action=toggle-filters]')
                Select(wait(driver, '#filter-intention')).select_by_value(value)

            def empty(driver):
                WebDriverWait(driver, 15).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.student-card')) == 0 and 'No more profiles for now.' in driver.find_element(By.ID, 'discovery-results').text)

            def open_profile(driver, selector='.dating-card .name-button'):
                click(driver, selector)
                wait(driver, '#dialog .dialog-body')
                WebDriverWait(driver, 15).until(lambda _: driver.execute_script('return !!document.querySelector("#dialog .test-label")'))

            def profile_data(driver, uid, context='dating'):
                return fetch(driver, '/api/profiles/' + uid + '?context=' + context)

            try:
                start()
                alice, brian = browser(mobile=True), browser()
                login(alice, 'alice')
                login(brian, 'brian')
                fill(brian, '#profile-form [name=program]', 'Business Administration')
                click(brian, '#profile-form button[type=submit]')
                text(brian, 'Profile and preferences saved.')
                activate(alice, 'relationship', True)
                activate(brian)
                alice_id, brian_id = me(alice)['id'], me(brian)['id']
                assert me(alice)['show_dating_intention'] is True
                assert me(brian)['dating_intention'] == ''
                search(alice, 'Brian')
                assert not alice.find_elements(By.CSS_SELECTOR, '.dating-card .dating-intention')
                search(brian, 'Alice')
                assert not brian.find_elements(By.CSS_SELECTOR, '.dating-card .dating-intention')
                open_profile(brian)
                assert brian.find_element(By.CSS_SELECTOR, '#dialog .dating-intention strong').text == 'Looking for a relationship'
                click(brian, '#dialog [data-action=close-dialog]')
                print('PASS: optional mobile setup, private-by-default sharing, consistent labels, and unset cross-program students remain discoverable', flush=True)

                filter_intention(alice, 'relationship')
                empty(alice)
                click(alice, '#search-filters [data-action=clear-filters]')
                assert Select(alice.find_element(By.ID, 'filter-intention')).first_selected_option.get_attribute('value') == ''
                search(alice, 'Brian')
                settings(brian)
                choice(brian, 'getting_to_know', False)
                submit(brian)
                filter_intention(alice, 'getting_to_know')
                empty(alice)
                assert me(brian)['dating_intention'] == 'getting_to_know'
                assert profile_data(alice, brian_id)['body']['profile'].get('dating_intention') is None
                click(alice, '[data-action=discover-mode][data-mode=friend]')
                assert not alice.find_elements(By.ID, 'filter-intention')
                search(alice, 'Brian')
                assert not alice.find_elements(By.CSS_SELECTOR, '.dating-intention')
                open_profile(alice, '.student-card .name-button')
                assert not alice.find_elements(By.CSS_SELECTOR, '#dialog .dating-intention')
                click(alice, '#dialog [data-action=close-dialog]')
                click(alice, '[data-action=discover-mode][data-mode=study]')
                search(alice, 'Brian')
                assert not alice.find_elements(By.ID, 'filter-intention')
                click(alice, '[data-action=discover-mode][data-mode=dating]')
                click(alice, '[data-action=toggle-filters]') if 'hidden' in alice.find_element(By.ID, 'search-filters').get_attribute('class') else None
                assert Select(alice.find_element(By.ID, 'filter-intention')).first_selected_option.get_attribute('value') == ''
                search(alice, 'Brian')
                print('PASS: intention filtering excludes hidden/unset choices only when selected; clear and mode changes reset it; Friends and Study omit the control and label', flush=True)

                search(brian, 'Alice')
                open_profile(brian)
                text(brian, 'Looking for a relationship')
                assert brian.find_element(By.CSS_SELECTOR, '#dialog .dating-intention strong').text == 'Looking for a relationship'
                brian.save_screenshot(str(output / 'intention-profile-desktop.png'))
                click(brian, '#dialog [data-action=close-dialog]')
                for context in ('general', 'friend', 'study'):
                    projection = profile_data(brian, alice_id, context)['body']['profile']
                    assert 'dating_intention' not in projection and 'dating_intention_label' not in projection
                filter_intention(brian, 'relationship')
                assert not brian.find_elements(By.CSS_SELECTOR, '.dating-card .dating-intention')
                open_profile(brian)
                assert brian.find_element(By.CSS_SELECTOR, '#dialog .dating-intention strong').text == 'Looking for a relationship'
                click(brian, '#dialog [data-action=close-dialog]')
                click(brian, '.dating-card [data-action=like]')
                text(brian, 'Like added.')
                click(alice, '.dating-card [data-action=like]')
                text(alice, 'It’s a match.')
                click(alice, '#dialog [data-action=open-chat]')
                wait(alice, '#message-input')
                click(brian, '[data-action=view-dating-matches]')
                click(brian, '[data-action=open-chat]')
                wait(brian, '#message-input').send_keys('I would like to get to know you!')
                open_profile(brian, '.chat-header [data-action=view-profile]')
                assert brian.find_element(By.CSS_SELECTOR, '#dialog .dating-intention strong').text == 'Looking for a relationship'
                click(brian, '#dialog [data-action=close-dialog]')
                print('PASS: the filter matches displayed labels, Dating full profiles/matches show them, general API projections omit them, and different intentions still permit mutual matching', flush=True)

                settings(alice)
                choice(alice, 'relationship', False)
                submit(alice)
                assert brian.find_element(By.ID, 'message-input').get_attribute('value') == 'I would like to get to know you!'
                open_profile(brian, '.chat-header [data-action=view-profile]')
                assert not brian.find_elements(By.CSS_SELECTOR, '#dialog .dating-intention')
                assert 'dating_intention' not in profile_data(brian, alice_id)['body']['profile']
                click(brian, '#dialog [data-action=close-dialog]')
                assert me(alice)['dating_intention'] == 'relationship'
                settings(alice)
                choice(alice, 'figuring_out', True)
                alice.execute_script('document.querySelector(".dating-intention-settings").scrollIntoView({block:"start"})')
                alice.save_screenshot(str(output / 'intention-settings-mobile.png'))
                submit(alice)
                open_profile(brian, '.chat-header [data-action=view-profile]')
                assert brian.find_element(By.CSS_SELECTOR, '#dialog .dating-intention strong').text == 'Still figuring it out'
                click(brian, '#dialog [data-action=close-dialog]')
                click(brian, '#composer button[type=submit]')
                click(alice, 'a[href="/chats"][data-nav]')
                text(alice, 'I would like to get to know you!')
                wait(alice, '#message-input').send_keys('Let us start with a conversation.')
                click(alice, '#composer button[type=submit]')
                text(brian, 'Let us start with a conversation.')
                print('PASS: hiding keeps the private choice, editing updates authorized profiles, chat drafts survive updates, and actual messages flow both ways', flush=True)

                settings(alice)
                choice(alice, '')
                assert not alice.find_element(By.NAME, 'show_dating_intention').is_selected()
                assert not alice.find_element(By.NAME, 'show_dating_intention').is_enabled()
                submit(alice)
                assert me(alice)['dating_intention'] == ''
                settings(alice)
                choice(alice, 'getting_to_know', True)
                alice.execute_cdp_cmd('Network.enable', {})
                alice.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': True, 'latency': 0, 'downloadThroughput': 0, 'uploadThroughput': 0})
                click(alice, '#dating-form button[type=submit]')
                WebDriverWait(alice, 15).until(lambda _: alice.find_element(By.CSS_SELECTOR, '#dating-form .form-error').is_displayed())
                assert Select(alice.find_element(By.NAME, 'dating_intention')).first_selected_option.get_attribute('value') == 'getting_to_know'
                assert alice.find_element(By.NAME, 'show_dating_intention').is_selected()
                alice.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
                submit(alice)
                server.kill()
                server.wait(timeout=5)
                start()
                alice.refresh()
                wait(alice, '#discovery-results')
                assert me(alice)['dating_intention'] == 'getting_to_know'
                assert me(alice)['show_dating_intention'] is True
                brian.refresh()
                click(brian, '.conversation-item')
                text(brian, 'Let us start with a conversation.')
                open_profile(brian, '.chat-header [data-action=view-profile]')
                assert brian.find_element(By.CSS_SELECTOR, '#dialog .dating-intention strong').text == 'Getting to know people'
                click(brian, '#dialog [data-action=close-dialog]')
                print('PASS: removing clears the choice; offline failure retains settings for retry; sessions, intentions and messages survive a crash/restart', flush=True)

                click(brian, '#chat-safety > summary')
                click(brian, '#chat-safety [data-action=confirm-block-dialog]')
                click(brian, '#dialog [data-action=block-student]')
                WebDriverWait(brian, 15).until(lambda _: not brian.find_elements(By.CSS_SELECTOR, '#composer'))
                assert profile_data(brian, alice_id)['status'] == 404
                assert profile_data(alice, brian_id)['status'] == 404
                assert not alice.execute_script('return document.documentElement.scrollWidth>innerWidth')
                for driver in drivers:
                    errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ['Uncaught', 'SyntaxError', 'violates the following Content Security Policy'])]
                    assert not errors, errors
                print('PASS: blocking revokes contextual Dating reads; the 390px layout fits and no uncaught JavaScript or CSP errors occur', flush=True)
            except BaseException:
                for index, driver in enumerate(drivers):
                    try:
                        driver.save_screenshot(str(output / f'intention-failure-{index}.png'))
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
