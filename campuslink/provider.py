"""Optional SheerID adapter; only canonical, live, bound results can approve."""
import hashlib
import hmac
import json
import os
import re
import threading
import time
import unicodedata
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .security import age, token_hash


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class SheerID:
    name='SheerID'
    def __init__(self):
        self.client_id=os.getenv('CAMPUSLINK_SHEERID_CLIENT_ID','')
        self._client_secret=os.getenv('CAMPUSLINK_SHEERID_CLIENT_SECRET','')
        self._webhook_secret=os.getenv('CAMPUSLINK_SHEERID_WEBHOOK_SECRET','')
        self.programs={kind:os.getenv('CAMPUSLINK_SHEERID_'+suffix+'_PROGRAM_ID','').lower()
                       for kind,suffix in (('student','STUDENT'),('adult','AGE'))}
        self.organization=os.getenv('CAMPUSLINK_SHEERID_ORGANIZATION_ID','').strip()
        self.live=os.getenv('CAMPUSLINK_VERIFICATION_LIVE','false')=='true'
        self.issues=[]
        if os.getenv('CAMPUSLINK_VERIFICATION_PROVIDER','')!='sheerid':self.issues.append('Select the external verification provider before enabling it.')
        if not self.client_id or not self._client_secret:self.issues.append('Configure the SheerID OAuth application.')
        if not all(re.fullmatch(r'[a-f0-9]{24}',value) for value in self.programs.values()):
            self.issues.append('Configure separate student and 18+ age program IDs.')
        if self.programs['student']==self.programs['adult']:self.issues.append('Student and age programs must be separate.')
        if not self.organization.isdigit() or int(self.organization or '0')<=0:self.issues.append('Configure the actual provider institution ID.')
        if not self._webhook_secret:self.issues.append('Configure the provider webhook secret.')
        if not self.live:self.issues.append('Live verification is disabled until provider coverage and programs are confirmed.')
        self.configured=not self.issues
        self._access='';self._expires=0;self._lock=threading.Lock()

    def _request(self,url,*,body=None,form=False,bearer=None):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in ('auth.sheerid.com','services.sheerid.com') or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ValueError('Invalid verification service address.')
        headers={'Accept':'application/json'}
        if bearer:headers['Authorization']='Bearer '+bearer
        data=None
        if body is not None:
            data=(urlencode(body) if form else json.dumps(body)).encode()
            headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
        try:
            with build_opener(NoRedirect()).open(Request(url,data=data,headers=headers),timeout=12) as response:
                raw=response.read(512001)
            if len(raw)>512000:raise ValueError()
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError()
            return result
        except Exception:
            raise ValueError('The verification provider is unavailable. Try again later.') from None

    def access_token(self):
        with self._lock:
            if time.monotonic()<self._expires:return self._access
            result=self._request('https://auth.sheerid.com/oauth/token',body={
                'grant_type':'client_credentials','audience':'https://services.sheerid.com/rest/',
                'client_id':self.client_id,'client_secret':self._client_secret},form=True)
            token=result.get('access_token')
            if not isinstance(token,str) or not token or any(c.isspace() for c in token):
                raise ValueError('The verification provider did not authorize the application.')
            self._access=token
            self._expires=time.monotonic()+max(1,min(int(result.get('expires_in',3600)),3600)-60)
            return token

    def api(self,path,body=None):
        return self._request('https://services.sheerid.com/rest/v2/'+path,body=body,bearer=self.access_token())

    def live_program(self,kind):
        if not self.configured:raise ValueError('External verification is not configured yet.')
        theme=self.api('program/'+self.programs[kind]+'/theme')
        config=theme.get('config',{})
        segment='student' if kind=='student' else 'age'
        if (not isinstance(config,dict) or theme.get('isTestMode') is not False or config.get('segment')!=segment
                or not isinstance(config.get('countries'),list) or 'ZM' not in config['countries']):
            raise ValueError('The provider program is not confirmed live for Zambia and this check.')
        if kind=='adult' and (type(config.get('minAge')) is not int or config['minAge']<18):
            raise ValueError('The age program must enforce a minimum age of at least 18.')
        return theme

    def create(self,kind):
        self.live_program(kind)
        result=self.api('verification',{'programId':self.programs[kind]})
        identifier=result.get('verificationId','')
        if not re.fullmatch(r'[a-f0-9]{24}',identifier):raise ValueError('The provider did not return a valid verification reference.')
        return identifier

    def hosted_url(self,kind,identifier):
        if kind not in self.programs or not re.fullmatch(r'[a-f0-9]{24}',identifier):raise ValueError('Invalid verification reference.')
        return 'https://services.sheerid.com/verify/'+self.programs[kind]+'/?'+urlencode({'verificationId':identifier})

    def details(self,kind,identifier):
        self.live_program(kind)
        if not re.fullmatch(r'[a-f0-9]{24}',identifier):raise ValueError('Invalid verification reference.')
        return self.api('verification/'+identifier+'/details')

    def signed_event(self,body,signature):
        if not self.configured or not re.fullmatch(r'[a-f0-9]{64}',signature):return None
        expected=hmac.new(self._webhook_secret.encode(),body,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,signature):return None
        try:
            event=json.loads(body)
            timestamp=event.get('timestamp')
            nonce=event.get('nonce','')
            if (type(timestamp) is not int or abs(time.time()-timestamp/1000)>300
                    or not isinstance(nonce,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',nonce)):return None
            if not re.fullmatch(r'[a-f0-9]{24}',event.get('verificationId','')):return None
            return event
        except (ValueError,TypeError,AttributeError):return None

    def evaluate(self,record,details):
        if not isinstance(details,dict):return {'status':'rejected','reason':'invalid_response'}
        last=details.get('lastResponse',{});person=details.get('personInfo',{})
        if not isinstance(last,dict) or not isinstance(person,dict):return {'status':'rejected','reason':'invalid_response'}
        if not record.get('live_started') or any(details.get(key) is True for key in ('isTestMode','testMode','testing')):
            return {'status':'rejected','reason':'test_result'}
        if (record['program_id']!=self.programs[record['kind']] or details.get('programId')!=record['program_id'] or last.get('verificationId')!=record['provider_id']
                or token_hash(str(person.get('email','')).lower())!=record['email_hash']):
            return {'status':'rejected','reason':'record_mismatch'}
        if last.get('currentStep')!='success':
            return {'status':'rejected' if last.get('currentStep') in ('error','expired','consolation') else 'pending','reason':'not_successful'}
        expected='student' if record['kind']=='student' else 'age'
        if last.get('segment')!=expected:return {'status':'rejected','reason':'wrong_check'}
        trustworthy={'authoritative','documentReview','sso'} if record['kind']=='student' else {'authoritative','documentReview'}
        sources=details.get('approvingVerificationTypes',[])
        if not isinstance(sources,list) or not all(isinstance(source,str) for source in sources) or not trustworthy.intersection(sources):
            return {'status':'rejected','reason':'insufficient_evidence'}
        dob=person.get('birthDate','')
        if not isinstance(dob,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',dob):return {'status':'rejected','reason':'missing_birth_date'}
        try:
            years=age(dob)
            if not 0<=years<=100:raise ValueError()
        except (ValueError,TypeError):return {'status':'rejected','reason':'missing_birth_date'}
        if record['kind']=='adult' and years<18:return {'status':'rejected','reason':'under_18'}
        if record['kind']=='student':
            segments=details.get('confirmedSegments',[])
            if not isinstance(segments,list):return {'status':'rejected','reason':'invalid_response'}
            valid=False;ends=[]
            for item in segments:
                if not isinstance(item,dict) or not isinstance(item.get('organization'),dict):continue
                end=item.get('endDate')
                current=end is None or end==0 or (type(end) in (int,float) and end/1000>time.time())
                if item.get('segment')=='student' and item.get('active') is True and str(item['organization'].get('id'))==self.organization and current:
                    valid=True
                    if type(end) in (int,float) and end>0:ends.append(int(end/1000))
            if not valid:return {'status':'rejected','reason':'wrong_or_inactive_institution'}
        if not all(isinstance(person.get(key),str) for key in ('firstName','lastName')):
            return {'status':'rejected','reason':'missing_identity_binding'}
        names=[unicodedata.normalize('NFKC',person[key]).strip().casefold() for key in ('firstName','lastName')]
        if not all(names):return {'status':'rejected','reason':'missing_identity_binding'}
        identity=token_hash('\0'.join(names+[dob]))
        result={'status':'approved','reason':'canonical_live_result','identity_hash':identity,'dob':dob}
        if record['kind']=='student' and ends:result['provider_expires_at']=min(ends)
        return result
