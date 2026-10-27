"""Optional real email delivery. Disabled unless the operator supplies SMTP config."""
from email.message import EmailMessage
import os
import re
import smtplib
import ssl
from urllib.parse import urlsplit


class SMTPRecovery:
    def __init__(self, *, base_url=None):
        self.host=os.getenv('CAMPUSLINK_SMTP_HOST','')
        self.sender=os.getenv('CAMPUSLINK_SMTP_FROM','')
        self.base=(base_url or os.getenv('CAMPUSLINK_BASE_URL','')).rstrip('/')
        self.user=os.getenv('CAMPUSLINK_SMTP_USER','')
        self._password=os.getenv('CAMPUSLINK_SMTP_PASSWORD','')
        self.issues=[]
        if not self.host:self.issues.append('Set CAMPUSLINK_SMTP_HOST to enable email delivery.')
        if not self.sender:self.issues.append('Set CAMPUSLINK_SMTP_FROM to an authorized sender address.')
        try:
            self.port=int(os.getenv('CAMPUSLINK_SMTP_PORT','587'))
            if not 1<=self.port<=65535:raise ValueError()
        except ValueError:
            self.port=587;self.issues.append('Set a valid CAMPUSLINK_SMTP_PORT.')
        self.tls=os.getenv('CAMPUSLINK_SMTP_TLS','ssl' if self.port==465 else 'starttls')
        if self.tls not in ('ssl','starttls'):
            self.issues.append('CAMPUSLINK_SMTP_TLS must be ssl or starttls.')
        if self.user and not self._password:
            self.issues.append('Set CAMPUSLINK_SMTP_PASSWORD for the configured SMTP account.')
        if self.host and (any(c.isspace() for c in self.host) or '://' in self.host):
            self.issues.append('CAMPUSLINK_SMTP_HOST must be a hostname without a URL scheme.')
        if self.sender and not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',self.sender):
            self.issues.append('Set a valid CAMPUSLINK_SMTP_FROM address.')
        parsed=urlsplit(self.base)
        self.configured=bool(not self.issues and self.host and self.sender and parsed.netloc and not parsed.username and not parsed.password and
                             (parsed.scheme=='https' or (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1'))))

    def __call__(self,email,token):
        self.send(email,'Reset your CampusLink password',
            'A password reset was requested for your CampusLink account. '
            'This link expires in 30 minutes and can be used once. '
            'If you did not request it, ignore this email.\n\n'+self.base+'/reset-password#'+token)

    def send(self,email,subject,body):
        if not self.configured:
            raise RuntimeError('Recovery email is not configured.')
        msg=EmailMessage()
        msg['Subject']=subject
        msg['From']=self.sender
        msg['To']=email
        msg.set_content(body)
        context=ssl.create_default_context()
        factory=smtplib.SMTP_SSL if self.tls=='ssl' else smtplib.SMTP
        extra={'context':context} if self.tls=='ssl' else {}
        with factory(self.host,self.port,timeout=15,**extra) as server:
            if self.tls=='starttls':server.starttls(context=context)
            if self.user:server.login(self.user,self._password)
            refused=server.send_message(msg)
            if refused:raise smtplib.SMTPRecipientsRefused(refused)
