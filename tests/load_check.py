"""Bounded 16-account TLS messaging exercise on disposable storage.

Run: .venv/bin/python -m tests.load_check
Never sends load to Render or uses real student accounts. This is a pilot-sized
regression, not a capacity benchmark or security audit.
"""
import asyncio
import json
import os
from pathlib import Path
import statistics
import tempfile
import time

import httpx

from .journey_browser import PASSWORD, ROOT
from .staging_browser import StagingJourney

async def exercise(j):
    clients=[httpx.AsyncClient(base_url=j.loopback,verify=j.tls,trust_env=False,timeout=15,
        headers={'Host':f'campuslink-staging.test:{j.port}'}) for _ in range(16)]
    latencies=[];responses=[];tasks=[]
    async def request(index,method,path,data=None,expected=200):
        started=time.perf_counter()
        result=await clients[index].request(method,'/api'+path,json=data)
        latencies.append((time.perf_counter()-started)*1000);responses.append(result.status_code)
        assert result.status_code==expected,(index,method,path,result.status_code,result.text[:150])
        return result.json()
    async def stream(index,ready,refreshed):
        async with clients[index].stream('GET','/api/events',timeout=30) as response:
            assert response.status_code==200
            async for line in response.aiter_lines():
                if line=='event: ready':ready.set()
                if line=='event: refresh':refreshed.set()
    try:
        ids=[]
        for i in range(16):
            data=await request(i,'POST','/auth/register',{'username':f'load_member_{i}',
                'display_name':f'Load member {i}','email':f'load_{i}@example.test','password':PASSWORD,'agreement':True})
            ids.append(data['user']['id']);clients[i].headers['X-CSRF-Token']=data['csrf']
            await request(i,'PATCH','/me',{'program':'Computer Science' if i%2==0 else 'Business Administration',
                'onboarding_step':6,'gender':'woman' if i%2==0 else 'man'})
            await request(i,'POST','/dating/test-eligibility',{'dob':'2002-06-15','adult_test_agreement':True})
            await request(i,'PATCH','/me',{'dating_enabled':True,'dating_genders':['man' if i%2==0 else 'woman']})
        relations=[]
        for i in range(0,16,2):
            first=await request(i,'POST',f'/dating/{ids[i+1]}/like',{})
            second=await request(i+1,'POST',f'/dating/{ids[i]}/like',{})
            assert not first['matched'] and second['matched']
            relations.extend([second['id']]*2)
        ready=[asyncio.Event() for _ in clients];refreshed=[asyncio.Event() for _ in clients]
        tasks=[asyncio.create_task(stream(i,ready[i],refreshed[i])) for i in range(16)]
        await asyncio.wait_for(asyncio.gather(*(item.wait() for item in ready)),10)
        # Every browser has an open SSE connection while writes, reads,
        # discovery queries and duplicate retries compete for the same worker.
        async def member_work(i):
            for turn in range(6):
                payload={'body':f'Load member {i}, message {turn}.','client_id':f'load-{i}-message-{turn}'}
                sent=await request(i,'POST',f'/chats/{relations[i]}/messages',payload)
                retry=await request(i,'POST',f'/chats/{relations[i]}/messages',payload)
                assert sent['message']['id']==retry['message']['id']
                await request(i,'GET','/chats')
                await request(i,'GET','/discover')
        await asyncio.gather(*(member_work(i) for i in range(16)))
        await asyncio.wait_for(asyncio.gather(*(item.wait() for item in refreshed)),5)
        for i in range(16):
            messages=(await request(i,'GET',f'/chats/{relations[i]}/messages'))['items']
            assert len(messages)==12 and len({(m['sender_id'],m['client_id']) for m in messages})==12
            assert {m['sender_id'] for m in messages}=={ids[i],ids[i^1]}
            await request(i,'POST',f'/chats/{relations[i]}/delivered',{'message_id':messages[-1]['id']})
            await request(i,'POST',f'/chats/{relations[i]}/read',{'message_id':messages[-1]['id']})
            await request(i,'GET',f'/chats/{relations[(i+2)%16]}/messages',expected=404)
            await request(i,'GET','/operator/status',expected=403)
            denied=await clients[i].post('/api/chats/'+relations[i]+'/messages',json={'body':'Forged send.','client_id':'csrf-load-test'},headers={'X-CSRF-Token':'bad'})
            assert denied.status_code==403
        # Close live streams before crash/restart, preserving the client cookies.
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True);tasks=[]
        j.stop(crash=True);j.start()
        for i in range(16):
            history=await request(i,'GET',f'/chats/{relations[i]}/messages')
            assert len(history['items'])==12 and history['receipts']['read']==history['items'][-1]['id']
            assert (await request(i,'GET','/me'))['user']['id']==ids[i]
        ordered=sorted(latencies)
        result={'accounts':16,'mutual_matches':8,'simultaneous_sse_connections':16,'saved_messages':96,
            'duplicate_retries':96,'http_requests':len(responses),'server_errors':sum(code>=500 for code in responses),
            'latency_ms':{'p50':round(statistics.median(ordered),2),'p95':round(ordered[int(.95*(len(ordered)-1))],2),
                          'p99':round(ordered[int(.99*(len(ordered)-1))],2)},
            'restart_sessions_and_history':True,'cross_conversation_access_denied':True,
            'real_hosted_service':False,'physical_devices':False,'capacity_claim':False}
        assert result['server_errors']==0
        (ROOT/'artifacts'/'load-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await asyncio.gather(*(client.aclose() for client in clients))

def run():
    with tempfile.TemporaryDirectory(prefix='campuslink-load-') as temp:
        j=StagingJourney(Path(temp))
        j.extra_env={key:'' for key in os.environ if key.startswith(('CAMPUSLINK_SMTP_','CAMPUSLINK_SHEERID_'))}
        j.extra_env.update({'CAMPUSLINK_BACKUPS_ENABLED':'false','CAMPUSLINK_MAIL_TOKEN_SECRET':'',
            'CAMPUSLINK_ELIGIBILITY_MODE':'preview','CAMPUSLINK_REQUIRE_APPROVAL':'false',
            'CAMPUSLINK_VERIFICATION_LIVE':'false'})
        try:j.start();asyncio.run(exercise(j))
        finally:j.close()

if __name__=='__main__':run()
