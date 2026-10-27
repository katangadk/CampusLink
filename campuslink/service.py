"""Public operator details; delivery credentials are never exposed here."""
from dataclasses import dataclass
from datetime import date, datetime
import os
import re
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ServiceSettings:
    operator_name: str
    support_email: str
    privacy_review_date: str
    student_email_domains: tuple

    @classmethod
    def load(cls):
        name = os.getenv('CAMPUSLINK_OPERATOR_NAME','').strip()
        email = os.getenv('CAMPUSLINK_SUPPORT_EMAIL','').strip().lower()
        reviewed = os.getenv('CAMPUSLINK_PRIVACY_REVIEW_DATE','').strip()
        if len(name)>120 or any(ord(c)<32 for c in name):
            raise RuntimeError('CAMPUSLINK_OPERATOR_NAME must be at most 120 printable characters.')
        if email and (len(email)>254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email)):
            raise RuntimeError('CAMPUSLINK_SUPPORT_EMAIL must be a valid contact email address.')
        if reviewed:
            try:
                if date.fromisoformat(reviewed)>datetime.now(ZoneInfo('Africa/Lusaka')).date():
                    raise ValueError()
            except ValueError:
                raise RuntimeError('CAMPUSLINK_PRIVACY_REVIEW_DATE must be an actual review date in YYYY-MM-DD format.') from None
        domains = []
        for value in os.getenv('CAMPUSLINK_STUDENT_EMAIL_DOMAINS','').split(','):
            domain = value.strip().lower()
            if not domain:
                continue
            if (len(domain)>253 or '.' not in domain
                    or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in domain.split('.'))):
                raise RuntimeError('CAMPUSLINK_STUDENT_EMAIL_DOMAINS must list exact domains, without @, wildcards or URLs.')
            domains.append(domain)
        return cls(name,email,reviewed,tuple(sorted(set(domains))))

    def public(self):
        return {'operator_name':self.operator_name,'support_email':self.support_email,
                'student_email_domains':list(self.student_email_domains),
                'privacy_notice_version':'2026-10-27'}
