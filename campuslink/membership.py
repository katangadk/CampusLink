"""Owner-controlled membership is authorization, not automatic age verification."""
import json

from fastapi import Request


def revoke_dating(con,uid,now,emit):
    rows=con.execute('SELECT low_id,high_id FROM relationships WHERE (low_id=? OR high_id=?) AND kind="dating" AND status IN ("pending","accepted")',(uid,uid)).fetchall()
    peers={value for row in rows for value in row}
    con.execute('UPDATE relationships SET status="removed",updated_at=? WHERE (low_id=? OR high_id=?) AND kind="dating" AND status IN ("pending","accepted")',(now(),uid,uid))
    con.execute('UPDATE users SET dating_enabled=0 WHERE id=?',(uid,))
    con.execute('DELETE FROM dating_likes WHERE sender=? OR target=?',(uid,uid))
    con.execute('UPDATE message_requests SET status="declined" WHERE (sender=? OR target=?) AND kind="dating" AND status="pending"',(uid,uid))
    emit(con,uid,*peers)


def revoke_connections(con,uid,now,emit):
    rows=con.execute('SELECT low_id,high_id FROM relationships WHERE (low_id=? OR high_id=?) AND status IN ("pending","accepted")',(uid,uid)).fetchall()
    peers={value for row in rows for value in row}
    con.execute('UPDATE relationships SET status="removed",updated_at=? WHERE (low_id=? OR high_id=?) AND status IN ("pending","accepted")',(now(),uid,uid))
    con.execute('UPDATE users SET dating_enabled=0 WHERE id=?',(uid,))
    con.execute('DELETE FROM dating_likes WHERE sender=? OR target=?',(uid,uid))
    con.execute('UPDATE message_requests SET status="declined" WHERE (sender=? OR target=?) AND status="pending"',(uid,uid))
    emit(con,uid,*peers)


def install_membership(app,*,db,auth,payload,fail,now,emit,eligibility):
    def owner(con,request):
        user,_=auth(con,request)
        if not con.execute('SELECT 1 FROM operator_roles WHERE user_id=?',(user['id'],)).fetchone():
            fail('Operator access required.',403)
        return user

    @app.get('/api/operator/members')
    def membership_queue(request: Request):
        with db() as con:
            owner(con,request)
            return {'approval_required':eligibility.requires_approval,'items':[dict(row) for row in con.execute(
                'SELECT u.id,u.email,u.username,u.display_name,u.program,u.status AS account_status,u.created_at,'
                'COALESCE(m.status,"pending") AS approval_status,m.reason,m.updated_at '
                'FROM users u LEFT JOIN membership_approvals m ON m.user_id=u.id '
                'ORDER BY CASE COALESCE(m.status,"pending") WHEN "pending" THEN 0 WHEN "approved" THEN 1 ELSE 2 END,u.created_at DESC LIMIT 200')]}

    @app.post('/api/operator/members/{uid}')
    async def membership_decision(uid: str,request: Request):
        data=await payload(request)
        action=data.get('action')
        if action not in ('approve','decline'):fail('Choose approve or decline.',422)
        reason=data.get('reason','')
        if action=='decline' and reason not in ('not_campus_member','unable_to_confirm','other'):
            fail('Choose a reason for declining membership.',422)
        with db(True) as con:
            operator=owner(con,request)
            target=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not target:fail('Account unavailable.',404)
            if target['status']!='active':fail('This account is not active.',409)
            status='approved' if action=='approve' else 'rejected'
            if eligibility.membership(con,target)['status']==status:
                return {'ok':True,'status':status}
            con.execute('INSERT INTO membership_approvals(user_id,status,reviewer_id,reason,updated_at) VALUES (?,?,?,?,?) '
                'ON CONFLICT(user_id) DO UPDATE SET status=excluded.status,reviewer_id=excluded.reviewer_id,reason=excluded.reason,updated_at=excluded.updated_at',
                (uid,status,operator['id'],reason if status=='rejected' else '',now()))
            con.execute('INSERT INTO operator_audit(actor_id,target_id,action,detail,created_at) VALUES (?,?,?,?,?)',
                (operator['id'],uid,'membership_'+action,json.dumps({'status':status,'reason':reason if status=='rejected' else ''}),now()))
            if status=='rejected':revoke_connections(con,uid,now,emit)
            emit(con,uid)
        return {'ok':True,'status':status}
