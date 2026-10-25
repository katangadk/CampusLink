"""Public likes, private comments, real receipts and photo posts on phone viewports.

Run: .venv/bin/python -m tests.social_browser
All actions use fictional accounts in a temporary database, never the live app.
"""
import json
from pathlib import Path
import tempfile
import time
import uuid

import httpx
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from campuslink.seed import seed, PASSWORD
from .journey_browser import Journey


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-social-') as directory:
        j = Journey(Path(directory))
        groups, clients = [], []

        def passed(label):
            groups.append(label)
            print('PASS: ' + label, flush=True)

        def client(name):
            c = httpx.Client(base_url=j.url, trust_env=False, timeout=10)
            clients.append(c)
            r = c.post('/api/auth/login', json={'email':name+'@campuslink.test','password':PASSWORD})
            r.raise_for_status(); c.headers['X-CSRF-Token'] = r.json()['csrf']
            return c, r.json()['user']['id']

        def login(driver, name):
            driver.get(j.url + '/login')
            j.fill(driver, '#auth-form [name=email]', name+'@campuslink.test')
            j.fill(driver, '#auth-form [name=password]', PASSWORD)
            j.click(driver, '#auth-form button[type=submit]')
            j.wait(driver, '#student-search')

        def nav(driver, destination):
            j.click(driver, f'.nav a[href="/{destination}"]')

        def search(driver, name):
            j.fill(driver, '#student-search', name)
            WebDriverWait(driver, 20).until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.dating-card')) == 1 and name in driver.find_element(By.CSS_SELECTOR, '.dating-card h3').text)

        def status(driver, mid, label):
            WebDriverWait(driver, 20).until(lambda _: driver.find_element(By.CSS_SELECTOR, f'[data-message-id="{mid}"] .message-status').text == label)

        def fits(driver):
            assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
            assert driver.execute_script('return [...document.querySelectorAll(".nav a")].every(a=>{const r=a.getBoundingClientRect();return r.width>=44&&r.height>=44})')

        try:
            seed(j.database); j.start()
            ca, aid = client('alice'); cb, bid = client('brian'); cc, _ = client('chipo')
            for c, gender, interested in ((ca,'woman','man'), (cb,'man','woman')):
                c.patch('/api/me', json={'dating_enabled':True,'gender':gender,'dating_genders':[interested]}).raise_for_status()
            a, b = j.browser(390, 844), j.browser(412, 915)
            a.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-color-scheme','value':'dark'}]})
            b.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-color-scheme','value':'light'}]})
            login(a, 'alice'); login(b, 'brian')
            assert [e.text.split('\n')[0] for e in a.find_elements(By.CSS_SELECTOR, '.nav a')] == ['Feed','Discover','Matches','Inbox','Profile']
            for driver in (a,b):
                assert not driver.find_elements(By.CSS_SELECTOR, '.campus-label,.campus-full')
                assert 'Live updates' not in driver.find_element(By.TAG_NAME, 'body').text
                fits(driver)
            search(a,'Brian')
            actions = a.find_element(By.CSS_SELECTOR,'.dating-card .profile-social-actions').text
            assert actions.splitlines() == ['Like','Comment','Inbox'], actions
            assert not a.find_elements(By.CSS_SELECTOR,'.dating-card [data-action=dismiss]')
            j.click(a,'.dating-card [data-action=like]'); j.text(a,'Like added.')
            nav(b,'profile')
            j.click(b,'[data-action=public-profile-likes]'); j.text(b,'Alice Banda')
            assert cc.get('/api/profiles/'+bid+'/likes').json()['items'][0]['id'] == aid
            j.click(b,'#dialog [data-action=close-dialog]')
            assert ca.get('/api/chats').json()['items'] == []
            passed('simple five-tab navigation; Like/Comment/Inbox cards; public like identities without a premature chat')

            nav(b,'discover'); search(b,'Alice')
            j.click(b,'.dating-card [data-action=private-comment]')
            j.fill(b,'#private-comment-form textarea','Private request: a hello after class.')
            j.click(b,'#private-comment-form [type=submit]')
            j.text(b,'Private comment sent to their inbox requests.')
            assert cc.get('/api/message-requests').json()['items'] == []
            assert cb.get('/api/chats').json()['items'] == []
            a.execute_cdp_cmd('Network.enable',{})
            a.execute_cdp_cmd('Network.setBlockedURLs',{'urls':[j.url+'/api/message-requests*']})
            a.execute_script('window.dispatchEvent(new Event("online"))')
            nav(a,'chats'); j.text(a,'Message requests could not refresh.')
            a.execute_cdp_cmd('Network.setBlockedURLs',{'urls':[]})
            j.click(a,'#message-requests [data-action=retry-data]')
            j.click(a,'.message-requests > summary')
            j.text(a,'Private request: a hello after class.')
            a.save_screenshot(str(j.output/'private-inbox-request-dark.png'))
            j.click(a,'[data-action=request-decision][data-command=accept]')
            j.wait(a,'#message-input'); j.text(a,'Private request: a hello after class.')
            rid = ca.get('/api/chats').json()['items'][0]['id']
            nav(b,'chats'); j.click(b,'.conversation-item'); j.wait(b,'#message-input')
            assert len(ca.get(f'/api/chats/{rid}/messages').json()['items']) == 1
            passed('private comments stay out of public views; only recipient acceptance opens chat and inserts the comment once')

            # Recipient goes to Feed, then loses network. Sender must remain Sent.
            nav(b,'feed'); j.wait(b,'#post-form')
            b.execute_cdp_cmd('Network.enable',{})
            b.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
            j.fill(a,'#message-input','Receipt check while the other device is offline.')
            j.click(a,'#composer [type=submit]')
            WebDriverWait(a,20).until(lambda _: len(ca.get(f'/api/chats/{rid}/messages').json()['items'])==2)
            mid = ca.get(f'/api/chats/{rid}/messages').json()['items'][-1]['id']
            status(a,mid,'Sent')
            b.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
            b.execute_script('window.dispatchEvent(new Event("online"))')
            status(a,mid,'Delivered')
            assert ca.get('/api/chats').json()['items'][0]['receipts']['read'] < mid
            nav(b,'chats'); j.wait(b,'#message-input')
            status(a,mid,'Read')
            fits(a); fits(b)
            a.save_screenshot(str(j.output/'chat-read-receipts-dark.png'))
            passed('actual Sent → Delivered → Read transitions: offline, received in inbox, then viewed in conversation')

            nav(a,'feed'); j.wait(a,'#post-form')
            j.fill(a,'#post-form textarea','Campus photo <img src=x onerror="window.postInjected=1">')
            image = Path(directory)/'campus-photo.png'
            Image.new('RGB',(600,760),'#597f6d').save(image)
            a.find_element(By.CSS_SELECTOR,'#post-form [type=file]').send_keys(str(image))
            j.wait(a,'.post-photo-preview img')
            # Lose only the acknowledgement after the server saves the post.
            a.execute_script('''window.originalPostFetch=window.fetch;window.losePostAck=true;window.fetch=async function(url,opts){const response=await window.originalPostFetch.apply(this,arguments);if(window.losePostAck&&url==='/api/posts'&&opts?.method==='POST'&&response.ok){window.losePostAck=false;await response.clone().text();throw new TypeError('Test lost acknowledgement');}return response;};''')
            j.click(a,'#post-form [type=submit]')
            WebDriverWait(a,20).until(lambda _: a.find_element(By.ID,'post-error').is_displayed())
            assert len(ca.get('/api/feed').json()['items']) == 1
            assert a.find_element(By.CSS_SELECTOR,'#post-form textarea').get_attribute('value').startswith('Campus photo')
            j.click(a,'#post-form [type=submit]'); j.wait(a,'.feed-post')
            a.execute_script('window.fetch=window.originalPostFetch')
            assert len(ca.get('/api/feed').json()['items']) == 1
            assert a.execute_script('return window.postInjected||null') is None
            assert not a.find_elements(By.CSS_SELECTOR,'.post-body img')
            row = ca.get('/api/feed').json()['items'][0]
            nav(b,'feed'); j.wait(b,'.feed-post'); j.wait(b,'.post-image')
            j.click(b,'.feed-post [data-feed-action=like]')
            WebDriverWait(b,20).until(lambda _: b.execute_script('return document.querySelector(".post-reactions")?.textContent.trim()')=='1 like')
            j.click(b,'.feed-post [data-feed-action=likes]'); j.text(b,'Brian Mwansa')
            j.click(b,'#dialog [data-action=close-dialog]')
            for driver in (a,b): fits(driver)
            a.save_screenshot(str(j.output/'campus-feed-dark.png')); b.save_screenshot(str(j.output/'campus-feed-light.png'))
            passed('photo posts persist once after a lost acknowledgement; public post likes, escaped text and light/dark phone layouts')

            j.click(b,'.feed-post [data-feed-action=comment]')
            j.fill(b,'#private-comment-form textarea','Private photo comment: great picture.')
            j.click(b,'#private-comment-form [type=submit]')
            j.wait(b,'#message-input'); j.text(b,'Private photo comment: great picture.')
            assert 'Private photo comment' not in str(cc.get('/api/feed').json())
            nav(a,'feed'); j.wait(a,'.feed-post'); j.click(a,'.feed-post [data-feed-action=options]')
            j.fill(a,'#edit-post-form textarea','Updated campus photo caption.')
            j.click(a,'#edit-post-form [type=submit]'); j.text(a,'Updated campus photo caption.')
            j.click(a,'.feed-post [data-feed-action=options]'); j.click(a,'[data-action=delete-post-dialog]'); j.click(a,'[data-action=delete-post]')
            WebDriverWait(a,20).until(lambda _: not a.find_elements(By.CSS_SELECTOR,'.feed-post'))
            assert cb.get(row['photo_url']).status_code == 404
            passed('post comments use the private inbox; authors can edit/delete; deleted photo URLs stop serving data')

            # No unsolicited song player or third-party media requests.
            assert not a.find_elements(By.CSS_SELECTOR,'iframe,audio')
            severe = [entry for d in (a,b) for entry in d.get_log('browser') if entry['level']=='SEVERE' and ('Uncaught' in entry['message'] or 'Content Security Policy' in entry['message'])]
            assert not severe, severe
            (j.output/'social-results.json').write_text(json.dumps({'groups':groups,'physical_devices':False,
                'viewports':['390×844 dark','412×915 light'],'music':False},indent=2)+'\n')
        except BaseException:
            for n, d in enumerate(j.drivers):
                try:
                    print('BROWSER',n,d.current_url,d.find_element(By.TAG_NAME,'body').text[-3000:],flush=True)
                    d.save_screenshot(str(j.output/f'social-failure-{n}.png'))
                except Exception:
                    pass
            raise
        finally:
            for c in clients: c.close()
            j.close()


if __name__ == '__main__':
    run()
