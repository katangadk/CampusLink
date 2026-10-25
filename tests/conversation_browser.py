"""Focused conversation UX: photo-open profiles, grouping, keyboard and scroll.

Run: .venv/bin/python -m tests.conversation_browser
Uses isolated fictional accounts and synthetic images on a temporary server.
"""
import io
import json
import re
import sqlite3
from pathlib import Path
import tempfile
import uuid

import httpx
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait

from .journey_browser import Journey, PASSWORD


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-conversation-') as directory:
        j = Journey(Path(directory))
        clients, groups = [], []

        def passed(label):
            groups.append(label)
            print('PASS: ' + label, flush=True)

        def setup(name, display, program, gender, interested, shared):
            client = httpx.Client(base_url=j.url, trust_env=False, timeout=10)
            clients.append(client)
            response = client.post('/api/auth/register', json={'username': name, 'display_name': display,
                'email': name + '@campuslink.test', 'password': PASSWORD, 'agreement': True})
            response.raise_for_status()
            client.headers['X-CSRF-Token'] = response.json()['csrf']
            response = client.patch('/api/me', json={'program': program, 'year': 2, 'onboarding_step': 6,
                'bio': display + ' BIO_DETAIL <img src=x onerror="window.profileInjected=1">',
                'subjects': 'Research', 'skills': 'Design', 'study_goals': 'Project collaboration',
                'interests': ['Reading', 'Music']})
            response.raise_for_status()
            response = client.post('/api/dating/test-eligibility', json={'dob': '2002-06-15', 'adult_test_agreement': True})
            response.raise_for_status()
            response = client.patch('/api/me', json={'dating_enabled': True, 'gender': gender,
                'dating_genders': [interested], 'dating_intention': 'relationship', 'show_dating_intention': shared})
            response.raise_for_status()
            catalog = client.get('/api/catalog').json()['prompts']
            # Catalog entries use stable IDs owned by the backend.
            response = client.put('/api/me/prompts', json={'prompts': [
                {'prompt_id': catalog[0]['id'], 'answer': display + ' PROMPT_DETAIL: a walk after class.'},
                {'prompt_id': catalog[1]['id'], 'answer': 'A good book and an interesting conversation.'}]})
            response.raise_for_status()
            image = io.BytesIO()
            Image.new('RGB', (400, 500), '#f2a4c7' if shared else '#43283f').save(image, 'PNG')
            response = client.post('/api/me/photos', content=image.getvalue(), headers={
                'Content-Type': 'image/png', 'X-Upload-Id': str(uuid.uuid4())})
            response.raise_for_status()
            return client

        def login(driver, name):
            driver.get(j.url + '/login')
            j.fill(driver, '#auth-form [name=email]', name + '@campuslink.test')
            j.fill(driver, '#auth-form [name=password]', PASSWORD)
            j.click(driver, '#auth-form button[type=submit]')
            j.wait(driver, '.dating-card')

        def send_api(client, rid, body):
            response = client.post(f'/api/chats/{rid}/messages', json={'body': body, 'client_id': str(uuid.uuid4())})
            response.raise_for_status()
            return response.json()['message']

        def fits(driver):
            assert driver.execute_script('return ! (document.documentElement.scrollWidth > innerWidth)')
            assert driver.execute_script('const a=document.querySelector("#composer").getBoundingClientRect(),b=document.querySelector(".sidebar").getBoundingClientRect(),s=document.querySelector("#chat-safety").getBoundingClientRect();return a.bottom<=s.top+1&&s.bottom<=b.top+1&&b.bottom<=(visualViewport?.height||innerHeight)+1')

        def readable_bubble(driver, selector):
            colors = driver.execute_script('const s=getComputedStyle(document.querySelector(arguments[0]));return [s.color,s.backgroundColor]', selector)
            def luminance(color):
                channels = [float(n)/255 for n in re.findall(r'[\d.]+', color)[:3]]
                linear = [n/12.92 if n <= .04045 else ((n+.055)/1.055)**2.4 for n in channels]
                return sum(n*w for n, w in zip(linear, (.2126, .7152, .0722)))
            a, b = sorted(luminance(color) for color in colors)
            assert (b+.05)/(a+.05) >= 4.5, (selector, colors)

        try:
            j.start()
            ca = setup('layout_ada', 'Layout Ada', 'Computer Science', 'woman', 'man', True)
            cb = setup('layout_ben', 'Layout Ben', 'Business Administration', 'man', 'woman', False)
            a, b = j.browser(390, 844), j.browser(412, 915)
            a.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
            b.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'light'}]})
            login(a, 'layout_ada')
            login(b, 'layout_ben')
            for viewer, name in ((a, 'Layout Ben'), (b, 'Layout Ada')):
                card = viewer.find_element(By.CSS_SELECTOR, '.dating-card')
                assert name in card.text and 'BIO_DETAIL' not in card.text and 'PROMPT_DETAIL' not in card.text
                assert not card.find_elements(By.CSS_SELECTOR, '.tags,.student-bio,.profile-prompts,.dating-intention,.reason')
                j.click(viewer, '.dating-photo-open')
                j.text(viewer, name + ' BIO_DETAIL')
                j.text(viewer, name + ' PROMPT_DETAIL')
                assert not viewer.find_elements(By.CSS_SELECTOR, '#dialog p img')
                assert viewer.execute_script('return window.profileInjected||null') is None
                assert all(not button.is_displayed() for button in viewer.find_elements(By.CSS_SELECTOR, '#dialog [data-action=report-profile],#dialog [data-action=confirm-block-dialog]'))
                assert bool(viewer.find_elements(By.CSS_SELECTOR, '#dialog .dating-intention')) == (viewer is b)
                j.click(viewer, '#dialog [data-action=close-dialog]')
            a.save_screenshot(str(j.output / 'discovery-compact-dark.png'))
            j.click(a, '[data-mode=friend]')
            j.wait(a, '.student-card')
            assert not a.find_elements(By.CSS_SELECTOR, '.student-card .profile-prompts,.student-card .tags,.student-card .student-bio')
            j.click(a, '.dating-photo-open')
            assert not a.find_elements(By.CSS_SELECTOR, '#dialog .dating-intention')
            j.click(a, '#dialog [data-action=close-dialog]')
            passed('compact Dating/Friends cards; tapping photos reveals complete safely rendered profiles and preserves intention privacy')

            rid = j.match(a, b, 'Layout Ada', 'Layout Ben')
            for driver in (a, b):
                assert driver.find_element(By.CSS_SELECTOR, '[data-starter-action=toggle]').get_attribute('aria-expanded') == 'false'
                assert driver.execute_script('return document.querySelector("#messages").getBoundingClientRect().height > innerHeight*.55')
                fits(driver)
            for driver in (a, b):
                assert not driver.find_elements(By.CSS_SELECTOR, '.message-options,[data-action=report-message]')
                assert not driver.find_element(By.ID, 'chat-safety').get_attribute('open')
                assert all(not button.is_displayed() for button in driver.find_elements(By.CSS_SELECTOR, '#chat-safety button'))
            j.click(b, '.chat-header [data-action=student-menu]')
            assert not b.find_elements(By.CSS_SELECTOR, '#dialog [data-action=report-profile],#dialog [data-action=confirm-block-dialog]')
            j.click(b, '#dialog [data-action=open-chat-safety]')
            assert b.find_element(By.ID, 'chat-safety').get_attribute('open')
            assert j.api(b, '/api/reports/mine')['items'] == []
            assert j.api(b, '/api/blocks')['items'] == []
            j.click(b, '#chat-safety > summary')
            j.fill(b, '#message-input', 'DRAFT kept while viewing the profile.')
            j.click(b, '.chat-profile')
            j.text(b, 'Layout Ada PROMPT_DETAIL')
            j.click(b, '#dialog [data-action=close-dialog]')
            assert b.find_element(By.ID, 'message-input').get_attribute('value') == 'DRAFT kept while viewing the profile.'
            for body in ('How was your lecture?', 'I finally finished that project.', 'How did yours go?'):
                send_api(ca, rid, body)
            for body in ('Finally submitted mine too 😅', 'Coffee after class?'):
                send_api(cb, rid, body)
            WebDriverWait(b, 20).until(lambda _: len(b.find_elements(By.CSS_SELECTOR, '[data-message-id]')) == 5)
            assert len(b.find_elements(By.CSS_SELECTOR, '.message.is-grouped')) == 3
            assert len(b.find_elements(By.CSS_SELECTOR, '.message-date')) == 1
            assert len(b.find_elements(By.CSS_SELECTOR, '.message-avatar .profile-photo-button')) == 1
            assert len(b.find_elements(By.CSS_SELECTOR, '.message-meta time')) == 2
            for driver in (a, b):
                WebDriverWait(driver, 15).until(lambda _, d=driver: len(d.find_elements(By.CSS_SELECTOR, '[data-message-id]')) == 5)
                readable_bubble(driver, '.message.own .bubble')
                readable_bubble(driver, '.message.incoming .bubble')
            a.save_screenshot(str(j.output / 'conversation-dark-mobile.png'))
            b.save_screenshot(str(j.output / 'conversation-light-mobile.png'))
            j.click(b, '.message-avatar .profile-photo-button')
            j.text(b, 'Layout Ada BIO_DETAIL')
            j.click(b, '#dialog [data-action=close-dialog]')
            assert b.find_element(By.ID, 'message-input').get_attribute('value').startswith('DRAFT kept')
            passed('focused phone chat, collapsed starters, grouped bubbles/date labels, sender-photo profile access and retained drafts')

            j.fill(b, '#message-input', 'A mobile first line')
            b.find_element(By.ID, 'message-input').send_keys(Keys.ENTER, 'and a second line', Keys.ENTER, 'and a third line')
            assert '\n' in b.find_element(By.ID, 'message-input').get_attribute('value')
            assert len(j.history(b, rid)) == 5, 'Mobile Return must not send prematurely.'
            assert b.find_element(By.ID, 'message-input').rect['height'] > 46
            j.click(b, '#composer button[type=submit]')
            j.text(a, 'and a third line')
            WebDriverWait(b, 15).until(lambda _: not b.find_element(By.ID, 'message-input').get_attribute('value'))
            b.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': 412, 'height': 430, 'deviceScaleFactor': 1, 'mobile': True})
            WebDriverWait(b, 15).until(lambda _: b.execute_script('return document.querySelector(".sidebar").getBoundingClientRect().bottom<=430'))
            fits(b)
            j.click(b, '#chat-safety > summary')
            fits(b)
            assert b.execute_script('const nav=document.querySelector(".sidebar").getBoundingClientRect();return [...document.querySelectorAll("#chat-safety button")].every(button=>{const r=button.getBoundingClientRect();return r.height>=44&&r.bottom<=nav.top+1;})')
            j.click(b, '#chat-safety > summary')
            b.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': 412, 'height': 915, 'deviceScaleFactor': 1, 'mobile': True})
            passed('mobile Return inserts newlines without sending; composer grows/resets and stays above navigation when the viewport shrinks')

            for index in range(55):
                send_api(ca, rid, f'History message {index:02d}')
            WebDriverWait(b, 25).until(lambda _: len(b.find_elements(By.CSS_SELECTOR, '[data-message-id]')) == 61)
            b.refresh()
            j.click(b, '.conversation-item')
            j.wait(b, '[data-action=older-messages]')
            assert len(b.find_elements(By.CSS_SELECTOR, '[data-message-id]')) == 50
            j.click(b, '[data-action=older-messages]')
            WebDriverWait(b, 15).until(lambda _: len(b.find_elements(By.CSS_SELECTOR, '[data-message-id]')) == 61)
            b.execute_script('document.querySelector("#messages").scrollTop=0')
            send_api(ca, rid, 'New while you read older history.')
            j.wait(b, '#new-message-jump:not([hidden])')
            assert b.execute_script('return document.querySelector("#messages").scrollTop') < 5
            j.click(b, '[data-action=jump-latest]')
            assert b.execute_script('const r=document.querySelector("#messages");return r.scrollHeight-r.scrollTop-r.clientHeight<5')
            ids = b.execute_script('return [...document.querySelectorAll("[data-message-id]")].map(e=>e.dataset.messageId)')
            assert len(ids) == len(set(ids)) == 62
            passed('history pagination keeps every message once; incoming messages preserve reading position with a working New messages shortcut')

            j.fill(b, '#message-input', 'A draft kept while reviewing safety options.')
            j.click(b, '#chat-safety > summary')
            assert j.api(b, '/api/reports/mine')['items'] == []
            assert j.api(b, '/api/blocks')['items'] == []
            j.click(b, '#chat-safety [data-action=report-conversation]')
            j.click(b, '#dialog [data-action=close-dialog]')
            assert j.api(b, '/api/reports/mine')['items'] == []
            assert b.find_element(By.ID, 'message-input').get_attribute('value') == 'A draft kept while reviewing safety options.'
            j.click(b, '#chat-safety [data-action=confirm-block-dialog]')
            j.click(b, '#dialog [data-action=close-dialog]')
            assert j.api(b, '/api/blocks')['items'] == []
            j.click(b, '#chat-safety [data-action=report-conversation]')
            choices = Select(b.find_element(By.CSS_SELECTOR, '#report-form [name=message_id]'))
            chosen = choices.options[1].get_attribute('value')
            choices.select_by_value(chosen)
            assert not b.execute_script('return document.documentElement.scrollWidth>innerWidth')
            j.fill(b, '#report-form [name=detail]', 'Synthetic message report for the UI audit.')
            j.click(b, '#report-form button[type=submit]')
            j.text(b, 'Report received.')
            assert len(j.api(b, '/api/reports/mine')['items']) == 1
            with sqlite3.connect(j.database) as con:
                assert con.execute('SELECT message_id FROM reports').fetchone()[0] == int(chosen)
            j.click(b, '#dialog [data-action=close-dialog]')
            j.click(b, '.chat-header [data-action=student-menu]')
            j.click(b, '#dialog [data-action=remove-connection]')
            j.click(b, '#dialog [data-action=confirm-remove]')
            j.revoked((a, b), rid)
            rid = j.match(a, b, 'Layout Ada', 'Layout Ben')
            assert not a.find_element(By.ID, 'chat-safety').get_attribute('open')
            a.find_element(By.CSS_SELECTOR, '#chat-safety > summary').send_keys(Keys.SPACE)
            assert a.find_element(By.ID, 'chat-safety').get_attribute('open')
            a.save_screenshot(str(j.output / 'chat-safety-open-dark.png'))
            j.click(a, '#chat-safety [data-action=confirm-block-dialog]')
            assert j.api(a, '/api/blocks')['items'] == []
            j.click(a, '#dialog [data-action=block-student]')
            j.revoked((a, b), rid)
            for driver in (a, b):
                errors = [entry for entry in driver.get_log('browser') if any(marker in entry['message'] for marker in ('Uncaught', 'SyntaxError', 'violates the following Content Security Policy'))]
                assert not errors, errors
            passed('collapsed footer stays optional; cancelled actions preserve drafts; selected-message reporting, unmatch and confirmed block enforce API access; no uncaught JS/CSP errors')
            (j.output / 'conversation-results.json').write_text(json.dumps({'groups': groups, 'physical_devices': False}, indent=2) + '\n')
        except BaseException:
            for index, driver in enumerate(j.drivers):
                driver.save_screenshot(str(j.output / f'conversation-failure-{index}.png'))
                print('BROWSER', index, driver.current_url, driver.find_element(By.TAG_NAME, 'body').text[-3500:], flush=True)
            raise
        finally:
            for client in clients:
                client.close()
            j.close()


if __name__ == '__main__':
    run()
