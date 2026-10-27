"""Subprocess-only synthetic mail transport; never contacts an SMTP provider."""
import json
import os
from pathlib import Path
from campuslink.app import create_app

class FileDelivery:
    configured=True
    issues=[]
    def send(self,email,subject,body):
        with Path(os.environ['CAMPUSLINK_QA_MAIL_FILE']).open('a') as stream:
            stream.write(json.dumps({'email':email,'subject':subject,'body':body})+'\n')

app=create_app(testing=True,recovery_delivery=FileDelivery())
