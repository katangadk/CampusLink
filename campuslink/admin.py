"""Grant or revoke staff access from a trusted server console, never via signup."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import time

from .operations import connect


def set_role(database, account, role, *, revoke=False):
    if role not in ('operator','moderator'):
        raise ValueError('Choose operator or moderator.')
    with closing(connect(database)) as con:
        con.execute('BEGIN IMMEDIATE')
        user = con.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE',
                           (account,account)).fetchone()
        if not user or user['status']!='active':
            raise ValueError('Create an active individual account before granting staff access.')
        if role=='operator':
            if revoke:
                con.execute('DELETE FROM operator_roles WHERE user_id=?',(user['id'],))
                con.execute('UPDATE users SET role="student" WHERE id=?',(user['id'],))
            else:
                con.execute('INSERT OR IGNORE INTO operator_roles VALUES (?,?)',(user['id'],int(time.time())))
                con.execute('UPDATE users SET role="moderator" WHERE id=?',(user['id'],))
                con.execute('INSERT OR REPLACE INTO service_state(key,value) VALUES ("membership_approval_activated","1")')
        else:
            if revoke and con.execute('SELECT 1 FROM operator_roles WHERE user_id=?',(user['id'],)).fetchone():
                raise ValueError('Revoke operator access before removing moderator access.')
            con.execute('UPDATE users SET role=? WHERE id=?',('student' if revoke else 'moderator',user['id']))
        con.execute('INSERT INTO operator_audit(actor_id,target_id,action,detail,created_at) VALUES (NULL,?,?,?,?)',
            (user['id'],('revoke_' if revoke else 'grant_')+role,'Trusted server console',int(time.time())))
        con.commit()
        return {'username':user['username'],'role':role,'revoked':revoke}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('grant','revoke'))
    parser.add_argument('role',choices=('operator','moderator'))
    parser.add_argument('account',help='Existing account username or email')
    parser.add_argument('--db',default=os.getenv('CAMPUSLINK_DB',str(Path(__file__).resolve().parent.parent/'data'/'campuslink.sqlite3')))
    args=parser.parse_args()
    try:
        result=set_role(args.db,args.account,args.role,revoke=args.command=='revoke')
    except (ValueError, OSError) as exc:
        parser.exit(1,str(exc)+'\n')
    print(('Revoked' if result['revoked'] else 'Granted')+' '+result['role']+' access for @'+result['username']+'.')


if __name__=='__main__':
    main()
