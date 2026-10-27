"""Exercise the hosted preview over real TLS with two isolated browsers.

Run: .venv/bin/python -m tests.staging_browser
Uses a temporary self-signed QA certificate, database and server.
It never changes the running app or creates a Render service.
"""
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import time

import httpx
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException

from campuslink.backup import backup_database
from .journey_browser import Journey, ROOT, PASSWORD


class StagingJourney(Journey):
    def __init__(self, temp):
        super().__init__(temp)
        self.url = f'https://campuslink-staging.test:{self.port}'
        self.loopback = f'https://127.0.0.1:{self.port}'
        self.native_challenges = {}
        self.cert, self.key = temp/'qa-cert.pem', temp/'qa-key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(self.key),
            '-out',str(self.cert),'-days','1','-subj','/CN=campuslink-staging.test',
            '-addext','subjectAltName=DNS:campuslink-staging.test,IP:127.0.0.1'],check=True,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.key.chmod(0o600)
        self.tls = ssl.create_default_context(cafile=str(self.cert))
        self.output = ROOT/'artifacts'/'staging'
        self.output.mkdir(parents=True,exist_ok=True)

    def http(self):
        return httpx.Client(base_url=self.loopback,trust_env=False,verify=self.tls,timeout=10,
            headers={'Host':f'campuslink-staging.test:{self.port}'})

    def start(self):
        env={**os.environ,'CAMPUSLINK_DB':str(self.database),'CAMPUSLINK_MODE':'staging',
             'CAMPUSLINK_BASE_URL':self.url,'CAMPUSLINK_REQUIRE_APPROVAL':'false',**getattr(self,'extra_env',{})}
        self.server=subprocess.Popen([sys.executable,'-m','uvicorn',getattr(self,'application','campuslink.app:app'),'--host','127.0.0.1',
            '--port',str(self.port),'--ssl-certfile',str(self.cert),'--ssl-keyfile',str(self.key),
            '--timeout-graceful-shutdown','2','--log-level','warning'],cwd=ROOT,env=env,stdout=self.log,stderr=self.log)
        with self.http() as c:
            for _ in range(100):
                if self.server.poll() is not None:break
                try:
                    if c.get('/api/health').is_success:return
                except httpx.RequestError:pass
                time.sleep(.1)
        raise RuntimeError('Hosted preview test server did not start.')

    def browser(self,width,height):
        opts=Options();opts.binary_location=shutil.which('chromium') or shutil.which('google-chrome')
        for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--no-proxy-server',
                     '--window-size=1280,1000','--host-resolver-rules=MAP campuslink-staging.test 127.0.0.1']:
            opts.add_argument(flag)
        # QA only: the temporary certificate is not a public certificate.
        opts.set_capability('acceptInsecureCerts',True)
        opts.set_capability('goog:loggingPrefs',{'browser':'ALL'})
        driver=webdriver.Chrome(service=Service(shutil.which('chromedriver')),options=opts)
        self.drivers.append(driver)
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
        driver.execute_cdp_cmd('Emulation.setTouchEmulationEnabled',{'enabled':True})
        driver.execute_cdp_cmd('Network.enable',{})
        # A native browser challenge is always a failure. No shared credentials
        # or Authorization headers are supplied to the browser.
        devtools, connection = driver.start_devtools()
        challenges = self.native_challenges[driver.session_id] = []
        def resume(event):
            try:connection.execute(devtools.fetch.continue_request(event.request_id))
            except WebDriverException as error:
                # A navigation can cancel an intercepted request before its
                # callback resumes it. Other protocol errors must still fail.
                if 'Invalid InterceptionId' not in str(error):raise
        connection.add_callback(devtools.fetch.RequestPaused,resume)
        def authenticate(event):
            challenges.append(event.request.url)
            response = devtools.fetch.AuthChallengeResponse(response='CancelAuth')
            connection.execute(devtools.fetch.continue_with_auth(event.request_id,response))
        connection.add_callback(devtools.fetch.AuthRequired,authenticate)
        connection.execute(devtools.fetch.enable(handle_auth_requests=True))
        return driver

    def register(self,driver,*args):
        driver.get(self.url+'/signup')
        self.wait(driver,'#auth-form')
        assert not driver.find_elements(By.CSS_SELECTOR,'[data-action=test-accounts]')
        self.text(driver,'Preview build.')
        user=super().register(driver,*args)
        self.click(driver,'[data-action=dating-settings]')
        self.wait(driver,'#dating-eligibility-form')
        assert not driver.find_elements(By.CSS_SELECTOR,'[data-action=dating-test-accounts]')
        self.click(driver,'#dialog [data-action=close-dialog]')
        assert any(c['name']=='campuslink_session' and c['secure'] and c['httpOnly'] for c in driver.get_cookies())
        return user


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-staging-') as directory:
        j=StagingJourney(Path(directory))
        try:
            j.start()
            with j.http() as c:
                assert c.get('/api/health').json()=={'status':'ok','mode':'staging','public_launch_ready':False}
                for path in ('/','/signup','/login','/assets/app.js','/api/catalog'):
                    response=c.get(path)
                    assert response.status_code==200 and 'WWW-Authenticate' not in response.headers
                    assert 'location' not in response.headers and 'set-cookie' not in response.headers
                for path in ('/api/me','/api/feed','/api/events','/api/photos/unknown'):
                    response=c.get(path)
                    assert response.status_code==401 and 'WWW-Authenticate' not in response.headers
            j.passed('HTTPS landing/signup/login/assets open directly; profiles, feed, photos and live events still require an individual account')
            a,b=j.browser(390,844),j.browser(412,915)
            for driver in (a,b):
                driver.get(j.url+'/signup')
                j.wait(driver,'#auth-form')
                assert not driver.find_elements(By.CSS_SELECTOR,'#tester-access-form')
                for _ in range(3):
                    j.api(driver,'/api/me',status=401)
                    j.api(driver,'/api/catalog')
                driver.get(j.url+'/login')
                j.fill(driver,'[name=email]','absent@campuslink.test')
                j.fill(driver,'[name=password]','Wrong-individual-password!')
                j.click(driver,'#auth-form [type=submit]')
                error=j.wait(driver,'#auth-form .form-error:not(.hidden)')
                assert 'Email or password is incorrect' in error.text
                driver.refresh()
                j.wait(driver,'#auth-form')
                assert not driver.get_cookies()
                assert len(j.native_challenges[driver.session_id])==0
            j.passed('direct signup/sign-in, clear wrong-account-password errors and refresh work without a tester form, shared cookies or native prompts')
            ua=j.register(a,'staging_ada','Staging Ada','Computer Science',2)
            ub=j.register(b,'staging_ben','Staging Ben','Business Administration',3)
            j.activate(a,'woman','man','relationship',True)
            j.activate(b,'man','woman','getting_to_know',False)
            rid=j.match(a,b,'Staging Ada','Staging Ben')
            j.passed('two independent secure sessions; fresh onboarding/photos/prompts and Dating setup; no demo login helpers; cross-program mutual match')
            j.send(a,'A hosted TLS message from Ada.');j.text(b,'A hosted TLS message from Ada.')
            j.send(b,'A hosted TLS reply from Ben.');j.text(a,'A hosted TLS reply from Ben.')
            j.fill(a,'#message-input','Keep this draft.');j.send(b,'An incoming message while a draft is open.')
            j.text(a,'An incoming message while a draft is open.')
            assert j.wait(a,'#message-input').get_attribute('value')=='Keep this draft.'
            a.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
            j.fill(a,'#message-input','One copy after an offline retry.');j.click(a,'#composer [type=submit]');j.wait(a,'[data-action=retry-message]')
            a.execute_cdp_cmd('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
            j.click(a,'[data-action=retry-message]');j.text(b,'One copy after an offline retry.')
            assert sum(m['body']=='One copy after an offline retry.' for m in j.history(b,rid))==1
            j.passed('authenticated SSE delivers both ways; drafts survive; TLS offline retry saves exactly one copy')
            photo=j.me(a)['main_photo_url']
            with j.http() as guest:
                assert guest.get(photo).status_code==401
            expected=j.history(a,rid)
            j.stop(crash=True);j.start()
            j.send(b,'A message after the hosted test restarts.');j.text(a,'A message after the hosted test restarts.')
            assert j.history(a,rid)[:-1]==expected
            a.refresh();j.click(a,'.conversation-item');j.text(a,'A message after the hosted test restarts.')
            assert j.me(a)['id']==ua['id'] and j.me(a)['main_photo_url']==photo
            j.passed('forced restart and refresh preserve secure sessions, profile images and complete chat history without a shared access gate')
            saved=backup_database(j.database,Path(directory)/'safe-backup.sqlite3')
            import sqlite3
            with sqlite3.connect(saved) as con:
                assert con.execute('PRAGMA quick_check').fetchone()[0]=='ok'
                assert con.execute('SELECT count(*) FROM users').fetchone()[0]==2
                assert con.execute('SELECT count(*) FROM messages').fetchone()[0]==5
                assert con.execute('SELECT count(*) FROM profile_photos').fetchone()[0]==2
            j.passed('online SQLite backup retains both users, five messages and processed photos with a passing integrity check')
            a.get(j.url+'/profile')
            j.click(a,'[data-action=logout]')
            j.wait(a,'#auth-form')
            j.api(a,'/api/me',status=401)
            j.fill(a,'[name=email]','staging_ada@campuslink.test')
            j.fill(a,'[name=password]',PASSWORD)
            j.click(a,'#auth-form [type=submit]')
            j.wait(a,'[data-action=notifications]')
            a.get(j.url+'/chats')
            j.wait(a,'.conversation-item')
            j.click(a,'.conversation-item')
            j.text(a,'A message after the hosted test restarts.')
            assert j.me(a)['id']==ua['id']
            j.passed('normal app logout and individual-password sign-in restore the same account and saved chat history, with no extra access step')
            j.click(a,'#chat-safety > summary');j.click(a,'#chat-safety [data-action=confirm-block-dialog]');j.click(a,'#dialog [data-action=block-student]')
            j.revoked((a,b),rid)
            j.api(b,photo,status=404)
            for d in (a,b):
                assert len(j.native_challenges[d.session_id])==0
                assert not d.execute_script('return document.documentElement.scrollWidth>innerWidth')
                errors=[e for e in d.get_log('browser') if any(t in e['message'] for t in ('Uncaught','SyntaxError','Content Security Policy'))]
                assert not errors,errors
            j.passed('student-level block rules still deny both clients and photo URLs; mobile layouts fit; no uncaught JS/CSP errors')
            (ROOT/'artifacts'/'staging-results.json').write_text(json.dumps({'groups':j.results,
                'temporary_tls_certificate':True,'real_hosted_service':False,'physical_devices':False,
                'native_auth_challenges_per_browser':[len(j.native_challenges[d.session_id]) for d in (a,b)],
                'fresh_test_accounts':2,'persisted_messages':5},indent=2)+'\n')
        except BaseException:
            for i,d in enumerate(j.drivers):
                try:
                    d.save_screenshot(str(j.output/f'failure-{i}.png'))
                    print('BROWSER',i,d.current_url,d.find_element(By.TAG_NAME,'body').text[-2200:],flush=True)
                except Exception:pass
            j.log.flush();j.log.seek(0);print(j.log.read()[-2500:],flush=True)
            raise
        finally:j.close()


if __name__=='__main__':run()
