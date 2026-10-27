"""Owner approval, mail links, private feedback and restored backup over QA TLS.

Run: .venv/bin/python -m tests.operations_browser
Temporary accounts, database and file mail transport only; no real email/provider.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from campuslink.admin import set_role
from campuslink.operations import restore_rehearsal
from .journey_browser import PASSWORD, ROOT
from .staging_browser import StagingJourney


def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-operations-') as directory:
        temp=Path(directory);j=StagingJourney(temp)
        j.application='tests.operations_fixture:app'
        j.extra_env={name:'' for name in os.environ if name.startswith(('CAMPUSLINK_SMTP_','CAMPUSLINK_SHEERID_'))}
        j.extra_env.update({'CAMPUSLINK_REQUIRE_APPROVAL':'auto','CAMPUSLINK_ELIGIBILITY_MODE':'preview',
            'CAMPUSLINK_VERIFICATION_LIVE':'false','CAMPUSLINK_BACKUPS_ENABLED':'false',
            'CAMPUSLINK_MAIL_TOKEN_SECRET':'Synthetic-browser-mail-key-for-QA-only-2026!',
            'CAMPUSLINK_QA_MAIL_FILE':str(temp/'mail.jsonl'),'CAMPUSLINK_SUPPORT_EMAIL':'support@example.test'})
        def register(name,program):
            with j.http() as c:
                response=c.post('/api/auth/register',json={'username':name,'display_name':name,
                    'email':name+'@example.test','password':PASSWORD,'agreement':True})
                assert response.status_code==200,response.text
                c.headers['X-CSRF-Token']=response.json()['csrf']
                assert c.patch('/api/me',json={'program':program,'onboarding_step':6}).status_code==200
                return response.json()['user']['id']
        def login(driver,name,password=PASSWORD):
            driver.get(j.url+'/login')
            j.fill(driver,'#auth-form [name=email]',name+'@example.test')
            j.fill(driver,'#auth-form [name=password]',password)
            j.click(driver,'#auth-form [type=submit]')
        def member_button(uid,status):return f'[data-operator=member][data-id="{uid}"][data-status={status}]'
        def latest_mail(subject):
            return WebDriverWait(member,20).until(lambda _:
                next((m for m in reversed([json.loads(line) for line in (temp/'mail.jsonl').read_text().splitlines()])
                    if subject in m['subject']),None) if (temp/'mail.jsonl').exists() else False)
        try:
            j.start()
            register('qa_owner','Computer Science')
            set_role(j.database,'qa_owner','operator')
            owner,member=j.browser(412,915),j.browser(390,844)
            downloads=temp/'downloads';downloads.mkdir()
            owner.execute_cdp_cmd('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
            login(owner,'qa_owner');owner.get(j.url+'/operator');j.text(owner,'Membership approvals')
            member.get(j.url+'/signup')
            for name,value in {'username':'qa_student','display_name':'QA student','email':'qa_student@example.test','password':PASSWORD}.items():
                j.fill(member,f'#auth-form [name={name}]',value)
            j.checked(member,'#auth-form [name=agreement]',True);j.click(member,'#auth-form [type=submit]')
            j.wait(member,'#onboarding-form[data-step="0"]')
            assert not member.find_elements(By.CSS_SELECTOR,'#profile-photo-file')
            j.click(member,'#onboarding-form [type=submit]')
            j.wait(member,'#onboarding-form[data-step="1"]')
            j.fill(member,'#onboarding-form [name=program]','Business Administration')
            j.click(member,'#onboarding-form [type=submit]:not([name=back])')
            for step in range(2,6):
                j.wait(member,f'#onboarding-form[data-step="{step}"]')
                j.click(member,'#onboarding-form [type=submit]:not([name=back])')
            j.text(member,'Waiting for campus approval');uid=j.me(member)['id']
            owner.refresh();j.text(owner,'Membership approvals')
            j.api(member,'/api/discover',status=403)
            j.click(owner,member_button(uid,'approve'));j.wait(owner,member_button(uid,'decline'))
            j.click(member,'[data-action=check-membership]');j.wait(member,'.dating-welcome')
            assert not j.me(member)['adult_eligible'] and not j.me(member)['verified']
            j.passed('trusted owner bootstrap activates membership approval; owner approves a pending account through the phone-sized console without granting verified age')

            member.get(j.url+'/verification');j.click(member,'[data-action=confirm-email-request]')
            mail=latest_mail('Confirm');member.get(mail['body'].splitlines()[-1])
            j.wait(member,'#verify-email-form');assert '#' not in member.current_url
            j.click(member,'#verify-email-form [type=submit]');j.text(member,'Email confirmed')
            status=j.api(member,'/api/verification')
            assert status['email_confirmed'] and not status['student_verified'] and not status['adult_verified']
            j.api(member,'/api/auth/verify-email','POST',{'token':mail['body'].rsplit('#',1)[-1]},status=400)
            member.get(j.url+'/profile');j.click(member,'[data-action=logout]')
            j.wait(member,'#auth-form')
            member.get(j.url+'/forgot-password');j.wait(member,'#recover-form')
            j.fill(member,'#recover-form [name=email]','qa_student@example.test');j.click(member,'#recover-form [type=submit]')
            reset=latest_mail('Reset');member.get(reset['body'].splitlines()[-1]);j.wait(member,'#reset-form')
            assert '#' not in member.current_url
            new_password='New-QA-individual-password-for-browser-2026!'
            j.fill(member,'#reset-form [name=new_password]',new_password);j.click(member,'#reset-form [type=submit]')
            j.wait(member,'#auth-form');login(member,'qa_student',new_password);j.wait(member,'.dating-welcome')
            j.passed('synthetic delivered email links confirm ownership and reset a password through the UI, clear URL fragments and cannot be reused')

            member.get(j.url+'/profile');j.click(member,'[data-action=pilot-feedback]');j.wait(member,'#feedback-form')
            feedback='The keyboard covers the send button. <script>window.feedbackAttack=true</script>'
            j.fill(member,'#feedback-form [name=body]',feedback);j.click(member,'#feedback-form [type=submit]')
            j.text(member,'Feedback sent');owner.refresh();j.text(owner,'The keyboard covers the send button.')
            assert owner.execute_script('return window.feedbackAttack') is None
            j.click(owner,'[data-operator=feedback][data-status=triaged]');j.text(owner,'triaged')
            assert j.api(member,'/api/feedback/mine')['items'][0]['status']=='triaged'
            j.passed('member feedback stays private, renders markup as text and can be triaged by the owner')

            # Opening and cancelling decline must not act on the member.
            j.click(owner,member_button(uid,'decline'));j.click(owner,'[data-operator=cancel-decline]')
            assert j.api(member,'/api/discover')['items']==[]
            j.click(owner,member_button(uid,'decline'));j.click(owner,'[data-operator=member-decline-confirm]')
            j.wait(owner,member_button(uid,'approve'))
            j.api(member,'/api/discover',status=403)
            member.get(j.url+'/discover');j.text(member,'Membership not approved')
            j.click(owner,member_button(uid,'approve'));j.wait(owner,member_button(uid,'decline'))
            j.click(member,'[data-action=check-membership]');j.wait(member,'.dating-welcome')
            j.passed('declining needs explicit confirmation; cancellation has no effect and re-approval restores discovery access')

            j.click(owner,'[data-operator=backup]');j.text(owner,'Last backup:');
            WebDriverWait(owner,20).until(lambda _:j.api(owner,'/api/operator/status')['operations']['runs'].get('backup',{}).get('status')=='ok')
            j.click(owner,'[data-operator=restore-check]')
            WebDriverWait(owner,20).until(lambda _:j.api(owner,'/api/operator/status')['operations']['runs'].get('restore',{}).get('status')=='ok')
            # Wait for the completed render rather than click a replaced node.
            WebDriverWait(owner,20).until(lambda _:'(ok)' in owner.find_element(By.CSS_SELECTOR,'#main').text)
            j.click(owner,'details:has(#operator-backup-download) > summary')
            j.fill(owner,'#operator-backup-download [name=password]',PASSWORD)
            j.click(owner,'#operator-backup-download [type=submit]');j.text(owner,'Download requested.')
            downloaded=downloads/'campuslink-backup.sqlite3'
            WebDriverWait(owner,20).until(lambda _:downloaded.is_file())
            checksum=hashlib.sha256(downloaded.read_bytes()).hexdigest()
            assert checksum in owner.find_element(By.CSS_SELECTOR,'[data-download-status]').text
            clipped=owner.execute_script('''return [...document.querySelectorAll('#main .panel, #main button, #main input')].filter(element=>{const rect=element.getBoundingClientRect();return rect.width>0&&(rect.left<0||rect.right>innerWidth+1)}).map(element=>element.tagName+':'+element.className)''')
            assert not clipped,clipped
            restored=restore_rehearsal(downloaded)
            assert restored['restore_verified'] and restored['counts']['users']==2
            owner.save_screenshot(str(j.output/'operator-console.png'))
            member.save_screenshot(str(j.output/'approved-discover.png'))
            j.passed('owner creates a backup, verifies a separate restore and downloads the checksum-matching SQLite file after password confirmation')
            for driver in (owner,member):
                assert not j.native_challenges[driver.session_id]
                assert not driver.execute_script('return document.documentElement.scrollWidth>innerWidth')
                errors=[entry for entry in driver.get_log('browser') if any(word in entry['message'] for word in ('Uncaught','SyntaxError','Content Security Policy'))]
                assert not errors,errors
            (ROOT/'artifacts'/'operations-results.json').write_text(json.dumps({'groups':j.results,
                'physical_devices':False,'real_email_delivery':False,'live_provider':False,'real_hosted_service':False},indent=2)+'\n')
        except BaseException:
            for i,driver in enumerate(j.drivers):
                try:
                    driver.save_screenshot(str(j.output/f'operations-failure-{i}.png'))
                    print('BROWSER',i,driver.current_url,driver.find_element(By.TAG_NAME,'body').text[-2200:],flush=True)
                except Exception:pass
            j.log.flush();j.log.seek(0);print(j.log.read()[-2000:],flush=True)
            raise
        finally:j.close()

if __name__=='__main__':run()
