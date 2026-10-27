"""Preview declarations and externally checked eligibility stay separate."""
from contextlib import closing
import os
import time

from .operations import connect
from .security import LocalEligibility, age, token_hash


class AccountEligibility:
    def __init__(self,database,service,*,hosted=False):
        self.database,self.service=database,service
        self.mode=os.getenv('CAMPUSLINK_ELIGIBILITY_MODE','preview')
        if self.mode not in ('preview','external'):
            raise RuntimeError('CAMPUSLINK_ELIGIBILITY_MODE must be preview or external.')
        approval=os.getenv('CAMPUSLINK_REQUIRE_APPROVAL','true' if self.mode=='external' else ('auto' if hosted else 'false'))
        if approval not in ('true','false','auto'):
            raise RuntimeError('CAMPUSLINK_REQUIRE_APPROVAL must be auto, true or false.')
        self.approval_policy=approval
        self._approval_activated=False
        self.preview=LocalEligibility()

    @property
    def requires_approval(self):
        if self.approval_policy!='auto':return self.approval_policy=='true'
        if not self._approval_activated:
            with closing(connect(self.database,readonly=True)) as con:
                self._approval_activated=bool(con.execute('SELECT 1 FROM service_state WHERE key="membership_approval_activated" AND value="1"').fetchone())
        return self._approval_activated

    def membership(self,con,user):
        row=con.execute('SELECT status,reason,updated_at FROM membership_approvals WHERE user_id=?',(user['id'],)).fetchone()
        return dict(row) if row else {'status':'pending','reason':'','updated_at':None}

    def approved(self,con,user):
        return not self.requires_approval or self.membership(con,user)['status']=='approved'

    def details(self,con,user):
        now=int(time.time())
        confirmation=con.execute('SELECT * FROM account_verification WHERE user_id=?',(user['id'],)).fetchone()
        confirmed=bool(confirmation and confirmation['email_hash']==token_hash(user['email'].lower()))
        domain=user['email'].rsplit('@',1)[-1].lower()
        allowed=not self.service.student_email_domains or domain in self.service.student_email_domains
        membership=self.membership(con,user)
        checks={row['kind']:dict(row) for row in con.execute('SELECT * FROM eligibility_checks WHERE user_id=?',(user['id'],))}
        def state(kind):
            row=checks.get(kind)
            if not row:return {'status':'not_started','expires_at':None}
            status=row['status']
            if status=='approved' and (row['method']!='provider' or not row['expires_at'] or row['expires_at']<=now):
                status='expired'
            return {'status':status,'expires_at':row['expires_at']}
        student,adult=state('student'),state('adult')
        return {'mode':self.mode,'email_confirmed':confirmed,'email_domain_allowed':allowed,
                'membership':membership,'approval_required':self.requires_approval,
                'student':student,'adult':adult,
                'student_verified':self.approved(con,user) and confirmed and allowed and student['status']=='approved',
                'adult_verified':adult['status']=='approved'}

    def student(self,user):
        if self.mode=='preview':
            if not self.preview.student(user):return False
            if not self.requires_approval:return True
            with closing(connect(self.database,readonly=True)) as con:return self.approved(con,user)
        with closing(connect(self.database,readonly=True)) as con:
            return self.details(con,user)['student_verified']

    def adult(self,user):
        if self.mode=='preview':return self.preview.adult(user) and self.student(user)
        try:
            old_enough=18<=age(user['dob'])<=100
        except (ValueError,TypeError):
            return False
        if not old_enough:return False
        with closing(connect(self.database,readonly=True)) as con:
            details=self.details(con,user)
            return details['student_verified'] and details['adult_verified']
