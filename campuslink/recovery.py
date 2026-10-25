"""Optional real email delivery. Disabled unless the operator supplies SMTP config."""
from email.message import EmailMessage
import os
import smtplib
import ssl
from urllib.parse import urlsplit


class SMTPRecovery:
    def __init__(self, *, base_url=None):
        self.host=os.getenv('CAMPUSLINK_SMTP_HOST','')
        self.sender=os.getenv('CAMPUSLINK_SMTP_FROM','')
        self.base=(base_url or os.getenv('CAMPUSLINK_BASE_URL','')).rstrip('/')
        parsed=urlsplit(self.base)
        self.configured=bool(self.host and self.sender and parsed.netloc and
                             (parsed.scheme=='https' or (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1'))))

    def __call__(self,email,token):
        if not self.configured:
            raise RuntimeError('Recovery email is not configured.')
        msg=EmailMessage()
        msg['Subject']='Reset your CampusLink password'
        msg['From']=self.sender
        msg['To']=email
        msg.set_content('A password reset was requested for your local CampusLink account. '
                        'This link expires in 30 minutes and can be used once. '
                        'If you did not request it, ignore this email.\n\n'+self.base+'/reset-password#'+token)
        with smtplib.SMTP(self.host,int(os.getenv('CAMPUSLINK_SMTP_PORT','587')),timeout=15) as server:
            server.starttls(context=ssl.create_default_context())
            user=os.getenv('CAMPUSLINK_SMTP_USER','')
            if user:
                server.login(user,os.environ['CAMPUSLINK_SMTP_PASSWORD'])
            server.send_message(msg)
