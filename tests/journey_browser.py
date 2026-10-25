"""Stage 6: two fresh accounts, real onboarding, dating, chat and consent.

Run: .venv/bin/python -m tests.journey_browser
Optional: CAMPUSLINK_JOURNEY_HOST=<computer Wi-Fi IPv4> to use a LAN HTTP
origin. All records and images belong to a temporary database, never the
running app's database. Phone viewports do not replace physical-device checks.
"""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

import httpx
from PIL import Image, ImageDraw
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


ROOT = Path(__file__).resolve().parent.parent
PASSWORD = 'Journey-local-test-2026!'


class Journey:
    def __init__(self, temp):
        self.temp = temp
        self.database = temp / 'journey.sqlite3'
        host = str(ipaddress.IPv4Address(os.getenv('CAMPUSLINK_JOURNEY_HOST', '127.0.0.1')))
        self.bind = '127.0.0.1' if host.startswith('127.') else '0.0.0.0'
        with socket.socket() as sock:
            sock.bind((self.bind, 0))
            self.port = sock.getsockname()[1]
        self.url = f'http://{host}:{self.port}'
        self.log = open(temp / 'server.log', 'w+')
        self.server = None
        self.drivers = []
        self.results = []
        self.output = ROOT / 'artifacts'
        self.output.mkdir(exist_ok=True)

    def start(self):
        env = {**os.environ, 'CAMPUSLINK_DB': str(self.database), 'CAMPUSLINK_MODE': 'local'}
        self.server = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'campuslink.app:app', '--host', self.bind,
             '--port', str(self.port), '--timeout-graceful-shutdown', '2', '--log-level', 'warning'],
            cwd=ROOT, env=env, stdout=self.log, stderr=self.log,
        )
        with httpx.Client(trust_env=False, timeout=.5) as client:
            for _ in range(100):
                if self.server.poll() is not None:
                    break
                try:
                    if client.get(self.url + '/api/health').is_success:
                        return
                except httpx.RequestError:
                    pass
                time.sleep(.1)
        raise RuntimeError('Journey test server did not start.')

    def stop(self, crash=False):
        if self.server and self.server.poll() is None:
            self.server.kill() if crash else self.server.terminate()
            try:
                self.server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=5)

    def close(self):
        for driver in self.drivers:
            driver.quit()
        self.stop()
        self.log.close()

    def browser(self, width, height):
        options = Options()
        options.binary_location = shutil.which('chromium') or shutil.which('google-chrome')
        for flag in ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
                     '--no-proxy-server', '--window-size=1280,1000']:
            options.add_argument(flag)
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        driver = webdriver.Chrome(service=Service(shutil.which('chromedriver')), options=options)
        self.drivers.append(driver)
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': True,
        })
        driver.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {'enabled': True})
        return driver

    def wait(self, driver, selector):
        return WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

    def click(self, driver, selector):
        def attempt(_):
            element = EC.element_to_be_clickable((By.CSS_SELECTOR, selector))(driver)
            if not element:
                return False
            driver.execute_script('arguments[0].scrollIntoView({block:"center"})', element)
            element.click()
            return True
        WebDriverWait(driver, 20, ignored_exceptions=(StaleElementReferenceException,)).until(attempt)

    def text(self, driver, value):
        WebDriverWait(driver, 20).until(lambda _: value in driver.find_element(By.TAG_NAME, 'body').text)

    def fill(self, driver, selector, value):
        field = self.wait(driver, selector)
        field.clear()
        field.send_keys(value)

    def checked(self, driver, selector, value):
        field = self.wait(driver, selector)
        if field.is_selected() != value:
            # Interest chips intentionally hide the native checkbox. Use its
            # visible label, as a person tapping the chip would.
            label = field.find_element(By.XPATH, 'ancestor::label[1]')
            driver.execute_script('arguments[0].scrollIntoView({block:"center"})', label)
            label.click()
            WebDriverWait(driver, 20).until(lambda _: self.wait(driver, selector).is_selected() == value)

    def api(self, driver, path, method='GET', data=None, status=200):
        result = driver.execute_async_script("""
            const [path, method, data, done] = arguments;
            (async () => {
              const options = {method, cache: 'no-store', headers: {}};
              if (method !== 'GET') {
                const me = await (await fetch('/api/me', {cache:'no-store'})).json();
                options.headers['X-CSRF-Token'] = me.user.csrf;
                options.headers['Content-Type'] = 'application/json';
                if (data !== null) options.body = JSON.stringify(data);
              }
              const response = await fetch(path, options);
              let body;
              if ((response.headers.get('content-type') || '').includes('application/json')) {
                body = await response.json();
              } else {
                body = {hex: Array.from(new Uint8Array(await response.arrayBuffer()),
                  byte => byte.toString(16).padStart(2, '0')).join('')};
              }
              done({status: response.status, body});
            })().catch(error => done({error: String(error)}));
        """, path, method, data)
        assert result.get('status') == status, (path, method, result)
        return result['body']

    def me(self, driver):
        return self.api(driver, '/api/me')['user']

    def passed(self, label):
        self.results.append(label)
        print('PASS: ' + label, flush=True)

    def register(self, driver, name, display, program, year):
        driver.get(self.url + '/signup')
        for field, value in {'display_name': display, 'username': name,
                             'email': name + '@campuslink.test', 'password': PASSWORD}.items():
            self.fill(driver, f'#auth-form [name={field}]', value)
        self.checked(driver, '#auth-form [name=agreement]', True)
        self.click(driver, '#auth-form button[type=submit]')
        self.wait(driver, '#onboarding-form[data-step="0"]')
        assert self.me(driver)['dating_enabled'] == 0
        image = Image.new('RGB', (420, 520), '#43283f' if year == 2 else '#f2a4c7')
        ImageDraw.Draw(image).text((30, 230), 'SYNTHETIC QA PHOTO\n' + display, fill='white')
        photo = self.temp / (name + '.png')
        image.save(photo)
        self.wait(driver, '#profile-photo-file').send_keys(str(photo))
        self.click(driver, '[data-photo-action=upload]')
        self.wait(driver, '.photo-tile')
        self.fill(driver, '#onboarding-form [name=bio]', 'Music, books, and meeting people beyond my course.')
        self.click(driver, '#onboarding-form button[type=submit]:not([name=back])')
        self.wait(driver, '#onboarding-form[data-step="1"]')
        self.fill(driver, '#onboarding-form [name=program]', program)
        Select(self.wait(driver, '#onboarding-form [name=year]')).select_by_visible_text(str(year))
        self.fill(driver, '#onboarding-form [name=subjects]', 'Research, Communication')
        self.click(driver, '#onboarding-form button[type=submit]:not([name=back])')
        self.wait(driver, '#onboarding-form[data-step="2"]')
        # Exercise persisted onboarding with an actual Back/Continue round trip.
        self.click(driver, '#onboarding-form [name=back]')
        self.wait(driver, '#onboarding-form[data-step="1"]')
        assert self.wait(driver, '[name=program]').get_attribute('value') == program
        self.click(driver, '#onboarding-form button[type=submit]:not([name=back])')
        self.wait(driver, '#onboarding-form[data-step="2"]')
        for interest in ('Music', 'Reading'):
            self.checked(driver, f'#onboarding-form [name=interests][value={interest}]', True)
        for step in range(2, 6):
            self.wait(driver, f'#onboarding-form[data-step="{step}"]')
            self.click(driver, '#onboarding-form button[type=submit]:not([name=back])')
        self.wait(driver, '.dating-welcome')
        self.click(driver, '.nav a[href="/profile"]')
        self.click(driver, '[data-prompt-action=add]')
        self.fill(driver, '#prompt-answer-0', f'{display}: a campus walk and a playlist swap.')
        self.click(driver, '[data-prompt-action=add]')
        self.fill(driver, '#prompt-answer-1', 'Ask me about the last book I could not put down.')
        self.click(driver, '[data-prompt-action=save]')
        self.text(driver, 'Answers saved.')
        user = self.me(driver)
        assert user['onboarding_step'] == 6 and user['program'] == program
        assert len(user['photos']) == 1 and len(user['prompts']) == 2
        assert not user['adult_eligible'] and not user['dating_enabled'] and not user['verified']
        return user

    def activate(self, driver, gender, interested, intention, displayed):
        self.click(driver, '[data-action=dating-settings]')
        self.wait(driver, '#dating-eligibility-form')
        driver.execute_script('document.querySelector("[name=dob]").value="2002-06-15"')
        self.checked(driver, '[name=adult_test_agreement]', True)
        self.click(driver, '#dating-eligibility-form button[type=submit]')
        self.wait(driver, '#dating-form')
        assert self.me(driver)['dating_enabled'] == 0, 'Adult declaration must not activate Dating.'
        Select(self.wait(driver, '#dating-form [name=gender]')).select_by_value(gender)
        self.checked(driver, f'#dating-form [name=dating_genders][value={interested}]', True)
        Select(self.wait(driver, '#dating-form [name=dating_intention]')).select_by_value(intention)
        self.checked(driver, '#dating-form [name=show_dating_intention]', displayed)
        self.checked(driver, '#dating-form [name=dating_enabled]', True)
        self.click(driver, '#dating-form button[type=submit]')
        self.wait(driver, '#student-search')
        assert self.me(driver)['verified'] is False

    def discover(self, driver, name):
        driver.get(self.url + '/discover')
        self.fill(driver, '#student-search', name)
        WebDriverWait(driver, 20).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.dating-card')) == 1
                                      and name in driver.find_element(By.CSS_SELECTOR, '.dating-card h3').text)

    def open_chat(self, driver):
        self.click(driver, '.nav a[href="/matches"]')
        self.click(driver, '.connection-card [data-action=open-chat]')
        self.wait(driver, '#composer')

    def send(self, driver, body):
        self.fill(driver, '#message-input', body)
        self.click(driver, '#composer button[type=submit]')
        WebDriverWait(driver, 20).until(lambda _: not self.wait(driver, '#message-input').get_attribute('value'))

    def history(self, driver, rid):
        return self.api(driver, f'/api/chats/{rid}/messages')['items']

    def revoked(self, drivers, rid):
        for driver in drivers:
            self.api(driver, f'/api/chats/{rid}/messages', status=403)
            self.api(driver, f'/api/chats/{rid}/starters', status=403)
            self.api(driver, f'/api/chats/{rid}/messages', 'POST',
                     {'body': 'This revoked send must not persist.', 'client_id': str(uuid.uuid4())}, status=403)
            assert self.api(driver, '/api/chats')['items'] == []
            WebDriverWait(driver, 20).until(lambda _: not driver.find_elements(By.CSS_SELECTOR, '#composer'))

    def match(self, a, b, name_a, name_b):
        self.discover(a, name_b)
        self.click(a, '.dating-card [data-action=like]')
        self.text(a, 'Like added.')
        assert self.api(a, '/api/chats')['items'] == []
        self.discover(b, name_a)
        self.click(b, '.dating-card [data-action=like]')
        self.text(b, 'It’s a match.')
        self.click(b, '#dialog [data-action=open-chat]')
        self.wait(b, '#composer')
        self.open_chat(a)
        return self.api(a, '/api/chats')['items'][0]['id']

    def exercise(self):
        self.start()
        a, b = self.browser(390, 844), self.browser(412, 915)
        ua = self.register(a, 'journey_a', 'Journey Ada', 'Computer Science', 2)
        ub = self.register(b, 'journey_b', 'Journey Ben', 'Business Administration', 3)
        assert ua['id'] != ub['id'] and ua['program'] != ub['program']
        with sqlite3.connect(self.database) as con:
            assert con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 2
        self.activate(a, 'woman', 'man', 'relationship', True)
        self.activate(b, 'man', 'woman', 'figuring_out', False)
        saved = {d: self.me(d) for d in (a, b)}
        hashes = {d: hashlib.sha256(bytes.fromhex(self.api(d, saved[d]['main_photo_url'])['hex'])).hexdigest()
                  for d in (a, b)}
        self.passed('two fresh registrations, six-step onboarding with Back, photos, two prompts, adult declaration and separate Dating opt-in')

        self.discover(a, 'Journey Ben')
        self.text(a, 'Business Administration')
        assert not a.find_elements(By.CSS_SELECTOR, '.dating-card .student-bio, .dating-card .profile-prompts, .dating-card .tags, .dating-card .dating-intention')
        self.click(a, '[data-action=toggle-filters]')
        self.fill(a, '#filter-program', 'Business Administration')
        Select(self.wait(a, '#filter-year')).select_by_value('3')
        Select(self.wait(a, '#filter-interest')).select_by_visible_text('Music')
        self.wait(a, '.dating-card')
        self.click(a, '.dating-card [data-action=view-profile]')
        self.text(a, 'Journey Ben: a campus walk')
        self.text(a, 'Ask me about the last book')
        assert len(a.find_elements(By.CSS_SELECTOR, '#dialog .profile-photo-gallery img')) == 1
        self.click(a, '#dialog [data-action=close-dialog]')
        for viewer, owner in ((a, ub), (b, ua)):
            general = self.api(viewer, '/api/profiles/' + owner['id'])['profile']
            dating = self.api(viewer, '/api/profiles/' + owner['id'] + '?context=dating')['profile']
            assert not {'email', 'dob', 'gender', 'dating_genders', 'csrf', 'dating_intention'} & general.keys()
            assert len(dating['prompts']) == 2
            assert ('dating_intention' in dating) == (owner['id'] == ua['id'])
            image_url = saved[a if owner['id'] == ua['id'] else b]['main_photo_url']
            self.api(viewer, image_url)
            with httpx.Client(trust_env=False) as guest:
                assert guest.get(self.url + image_url).status_code == 401
                assert guest.get(self.url + '/api/profiles/' + owner['id']).status_code == 401
        self.passed('cross-program filtered discovery, full photos/prompts, visible-only Dating intentions and direct anonymous/private-field checks')

        before = self.api(b, '/api/notifications')['items']
        self.click(a, '.dating-card [data-action=like]')
        self.text(a, 'Like added.')
        assert self.api(b, '/api/notifications')['items'] == before
        for driver in (a, b):
            assert self.api(driver, '/api/connections')['items'] == []
            assert self.api(driver, '/api/chats')['items'] == []
        self.discover(b, 'Journey Ada')
        self.click(b, '.dating-card [data-action=like]')
        self.text(b, 'It’s a match.')
        self.click(b, '#dialog [data-action=open-chat]')
        self.wait(b, '#composer')
        self.open_chat(a)
        rid = self.api(a, '/api/chats')['items'][0]['id']
        for driver, target in ((a, ub), (b, ua)):
            repeated = self.api(driver, '/api/dating/' + target['id'] + '/like', 'POST', {})
            assert repeated == {'matched': True, 'id': rid}
            matches = self.api(driver, '/api/connections')['items']
            assert len(matches) == 1 and matches[0]['kind'] == 'dating'
        self.passed('one-sided likes reveal no match/notification; mutual and repeated likes create exactly one dating match')

        assert self.wait(a, '[data-starter-action=toggle]').get_attribute('aria-expanded') == 'false'
        self.click(a, '[data-starter-action=toggle]')
        self.wait(a, '.starter-choice')
        draft = a.find_element(By.CSS_SELECTOR, '.starter-choice span').text
        self.click(a, '.starter-choice')
        assert self.wait(a, '#message-input').get_attribute('value') == draft
        assert self.history(a, rid) == []
        first = draft + ' I would enjoy hearing your answer.'
        self.send(a, first)
        self.text(b, first)
        self.fill(a, '#message-input', 'A draft safe while the other person replies.')
        reply = 'Let us swap playlists after class.'
        self.send(b, reply)
        self.text(a, reply)
        assert a.find_element(By.ID, 'message-input').get_attribute('value') == 'A draft safe while the other person replies.'
        assert len(self.history(a, rid)) == 2
        self.passed('starters require explicit Send; live messages work both ways and preserve an existing draft')

        a.execute_cdp_cmd('Network.enable', {})
        a.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': True, 'latency': 0, 'downloadThroughput': 0, 'uploadThroughput': 0})
        offline = 'An offline message retried exactly once.'
        self.fill(a, '#message-input', offline)
        self.click(a, '#composer button[type=submit]')
        self.wait(a, '[data-action=retry-message]')
        assert len(self.history(b, rid)) == 2
        assert self.wait(a, '#message-input').get_attribute('value') == offline
        a.execute_cdp_cmd('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        self.click(a, '[data-action=retry-message]')
        self.text(b, offline)
        WebDriverWait(a, 20).until(lambda _: not a.find_elements(By.CSS_SELECTOR, '[data-action=retry-message]'))
        assert sum(m['body'] == offline for m in self.history(a, rid)) == 1

        # Commit the real POST, then simulate loss of its successful response.
        a.execute_script("""
            const original = window.fetch;
            // Temporarily fail sender-side history reads as well. Otherwise
            // SSE correctly confirms the saved message before a person can
            // press Retry, and this would only exercise automatic recovery.
            window.journeyHoldHistory = true;
            window.fetch = async function(input, options) {
              if (window.journeyHoldHistory && String(input).includes('/messages') &&
                  (!options?.method || options.method === 'GET')) {
                throw new TypeError('Simulated temporary history outage');
              }
              const response = await original.call(this, input, options);
              if (!window.journeyAckLost && String(input).endsWith('/messages') &&
                  options?.method === 'POST' && response.ok) {
                window.journeyAckLost = true;
                throw new TypeError('Simulated loss of acknowledgement after commit');
              }
              return response;
            };
        """)
        ambiguous = 'The server saved this even though its acknowledgement was lost.'
        self.fill(a, '#message-input', ambiguous)
        self.click(a, '#composer button[type=submit]')
        self.wait(a, '[data-action=retry-message]')
        self.text(b, ambiguous)
        committed = [m for m in self.history(b, rid) if m['body'] == ambiguous]
        assert len(committed) == 1 and a.execute_script('return window.journeyAckLost')
        self.click(a, '[data-action=retry-message]')
        WebDriverWait(a, 20).until(lambda _: not a.find_elements(By.CSS_SELECTOR, '[data-action=retry-message]'))
        a.execute_script('window.journeyHoldHistory = false; window.dispatchEvent(new Event("online"));')
        assert [m for m in self.history(a, rid) if m['body'] == ambiguous] == committed
        self.passed('offline retry and a lost success acknowledgement preserve the retry key and save exactly one message')

        expected = self.history(a, rid)
        for driver in (a, b):
            assert not driver.execute_script('return document.documentElement.scrollWidth > innerWidth')
            assert driver.execute_script('return document.querySelector("#composer button").getBoundingClientRect().bottom <= (visualViewport?.height || innerHeight)')
            assert driver.execute_script('return [...document.querySelectorAll("[data-profile-photo]")].every(img=>img.complete && img.naturalWidth>0)')
        a.save_screenshot(str(self.output / 'journey-chat-mobile.png'))
        self.stop(crash=True)
        self.start()
        self.send(b, 'A message after the server crash and restart.')
        self.text(a, 'A message after the server crash and restart.')
        assert self.history(a, rid)[:-1] == expected
        for driver in (a, b):
            driver.refresh()
            self.click(driver, '.conversation-item')
            self.text(driver, ambiguous)
            user = self.me(driver)
            for key in ('id', 'program', 'onboarding_step', 'photos', 'prompts', 'dating_intention', 'show_dating_intention'):
                assert user[key] == saved[driver][key], key
            image = bytes.fromhex(self.api(driver, user['main_photo_url'])['hex'])
            assert hashlib.sha256(image).hexdigest() == hashes[driver]
            assert len(self.history(driver, rid)) == 5
        self.passed('forced server crash/restart reconnects live clients; refresh restores sessions, profiles, photos, prompts, intentions and all saved messages')

        # A hidden profile stays available to its accepted match, then disappears
        # once that consent is removed. Test direct URLs rather than UI alone.
        self.click(a, '.nav a[href="/profile"]')
        self.checked(a, '#profile-form [name=discoverable]', False)
        self.click(a, '#profile-form button[type=submit]')
        self.text(a, 'Profile and preferences saved.')
        self.api(b, '/api/profiles/' + ua['id'] + '?context=dating')
        self.api(b, saved[a]['main_photo_url'])
        self.open_chat(a)
        self.click(a, '.nav a[href="/matches"]')
        self.click(a, '[data-action=remove-connection]')
        self.click(a, '#dialog [data-action=confirm-remove]')
        self.revoked((a, b), rid)
        self.api(b, '/api/profiles/' + ua['id'], status=404)
        self.api(b, '/api/profiles/' + ua['id'] + '?context=dating', status=404)
        self.api(b, saved[a]['main_photo_url'], status=404)
        self.api(a, saved[a]['main_photo_url'])
        self.click(a, '.nav a[href="/profile"]')
        self.checked(a, '#profile-form [name=discoverable]', True)
        self.click(a, '#profile-form button[type=submit]')
        self.text(a, 'Profile and preferences saved.')
        self.passed('Unmatch closes both clients and denies direct read/send/starters; hidden-profile photos require current consent')

        rid = self.match(a, b, 'Journey Ada', 'Journey Ben')
        self.click(a, '.nav a[href="/profile"]')
        self.click(a, '[data-action=dating-settings]')
        self.checked(a, '#dating-form [name=dating_enabled]', False)
        self.click(a, '#dating-form button[type=submit]')
        self.wait(a, '.dating-welcome')
        self.revoked((a, b), rid)
        self.api(b, '/api/profiles/' + ua['id'] + '?context=dating', status=404)
        self.click(a, '[data-action=dating-settings]')
        self.checked(a, '#dating-form [name=dating_enabled]', True)
        self.click(a, '#dating-form button[type=submit]')
        self.wait(a, '#student-search')
        assert self.api(a, '/api/chats')['items'] == []
        assert self.api(b, '/api/chats')['items'] == []
        self.passed('disabling Dating revokes chat and Dating profile access; re-enabling restores no match without fresh mutual likes')

        rid = self.match(a, b, 'Journey Ada', 'Journey Ben')
        self.click(a, '#chat-safety > summary')
        self.click(a, '#chat-safety [data-action=confirm-block-dialog]')
        self.click(a, '#dialog [data-action=block-student]')
        self.revoked((a, b), rid)
        for viewer, owner, owner_driver in ((a, ub, b), (b, ua, a)):
            self.api(viewer, '/api/profiles/' + owner['id'], status=404)
            self.api(viewer, '/api/profiles/' + owner['id'] + '?context=dating', status=404)
            self.api(viewer, saved[owner_driver]['main_photo_url'], status=404)
            assert self.api(viewer, '/api/discover?mode=dating')['items'] == []
        self.api(a, '/api/blocks/' + ub['id'], 'DELETE')
        self.revoked((a, b), rid)
        for driver in (a, b):
            errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message']
                      for marker in ('Uncaught', 'SyntaxError', 'violates the following Content Security Policy'))]
            assert not errors, errors
        with sqlite3.connect(self.database) as con:
            assert con.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 5
            assert con.execute('SELECT COUNT(*) FROM relationships').fetchone()[0] == 1
        self.passed('blocking denies profiles/photos/chat in both directions; unblocking restores no consent; no duplicate or unauthorized messages or uncaught JS/CSP errors')
        return {'origin': self.url, 'phone_viewports': ['390x844', '412x915'],
                'insecure_http_origin': not a.execute_script('return window.isSecureContext'),
                'physical_phones_tested': False, 'fresh_accounts': 2, 'persisted_messages': 5,
                'passed_groups': self.results, 'completed_at': datetime.now(timezone.utc).isoformat()}


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-journey-') as directory:
        journey = Journey(Path(directory))
        try:
            result = journey.exercise()
            (journey.output / 'journey-results.json').write_text(json.dumps(result, indent=2) + '\n')
            print(f'PASS: all {len(journey.results)} combined journey groups on {journey.url}; physical-phone acceptance remains separate.', flush=True)
        except BaseException:
            for index, driver in enumerate(journey.drivers):
                try:
                    driver.save_screenshot(str(journey.output / f'journey-failure-{index}.png'))
                    print('BROWSER', index, driver.current_url, driver.find_element(By.TAG_NAME, 'body').text[-3000:], flush=True)
                except Exception:
                    pass
            journey.log.flush()
            journey.log.seek(0)
            print(journey.log.read()[-4000:], flush=True)
            raise
        finally:
            journey.close()


if __name__ == '__main__':
    run()
