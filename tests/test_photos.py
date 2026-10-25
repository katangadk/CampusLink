from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import struct
import uuid
import zlib

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
import pytest

from campuslink.app import create_app
from campuslink.photos import MAX_STORED_BYTES, MAX_UPLOAD_BYTES
from campuslink.seed import PASSWORD
from .conftest import Student, accepted, sql


def image_bytes(color='purple', size=(320,400), fmt='PNG', *, metadata=False):
    output=BytesIO()
    image=Image.new('RGB',size,color)
    options={}
    if metadata and fmt=='JPEG':
        exif=Image.Exif()
        exif[274]=6
        exif[315]='Private photographer'
        exif[270]='Private location metadata'
        options['exif']=exif
    if metadata and fmt=='PNG':
        info=PngImagePlugin.PngInfo()
        info.add_text('GPSLatitude','-15.4')
        options['pnginfo']=info
    image.save(output,fmt,**options)
    return output.getvalue()


def upload(student, content=None, *, photo_id=None, key=None):
    return student.client.request('PUT' if photo_id else 'POST','/api/me/photos'+('/'+photo_id if photo_id else ''),
        content=image_bytes() if content is None else content,
        headers={'Content-Type':'image/png','X-Upload-Id':key or str(uuid.uuid4())})


@pytest.mark.parametrize('fmt',['JPEG','PNG','WEBP'])
def test_photos_decode_resize_strip_metadata_and_survive_restart(students,app,fmt):
    a,b=students['alice'],students['brian']
    response=upload(a,image_bytes(size=(1800,2400),fmt=fmt,metadata=fmt!='WEBP'))
    assert response.status_code==200,response.text
    user=response.json()['user']
    assert len(user['photos'])==1 and user['main_photo_url']==user['photos'][0]['url']
    url=user['main_photo_url']
    viewed=b.client.get(url)
    assert viewed.status_code==200
    assert viewed.headers['Content-Type']=='image/jpeg' and viewed.headers['Cache-Control']=='no-store'
    assert len(viewed.content)<=MAX_STORED_BYTES
    with Image.open(BytesIO(viewed.content)) as image:
        assert image.format=='JPEG' and max(image.size)<=1200
        assert not image.getexif()
        assert 'GPSLatitude' not in image.info
        # EXIF rotation is respected before resizing.
        assert image.size==((1200,900) if fmt=='JPEG' else (900,1200))
    recreated=create_app(app.state.db_path,testing=True)
    a2=Student(recreated,'alice')
    assert a2.get('/me').json()['user']['main_photo_url']==url
    assert a2.client.get(url).content==viewed.content


def test_order_main_replace_and_delete_preserve_gallery_invariants(students):
    a=students['alice']
    first=upload(a).json()['photo_id']
    second=upload(a,image_bytes('blue')).json()['photo_id']
    third=upload(a,image_bytes('green')).json()['photo_id']
    r=a.post(f'/me/photos/{third}/main')
    assert [p['id'] for p in r.json()['user']['photos']]==[third,first,second]
    r=a.client.patch('/api/me/photos/order',json={'photo_ids':[second,third,first]})
    assert r.status_code==200
    assert [p['id'] for p in r.json()['user']['photos']]==[second,third,first]
    before=r.json()['user']['main_photo_url']
    r=upload(a,image_bytes('red'),photo_id=second)
    assert r.status_code==200
    assert r.json()['user']['main_photo_url']!=before
    assert r.json()['user']['photos'][0]['id']==second
    with Image.open(BytesIO(a.client.get(before).content)) as photo:
        red,green,blue=photo.getpixel((100,100))
        assert red>200 and green<30 and blue<30
    r=a.client.delete('/api/me/photos/'+second)
    assert [p['id'] for p in r.json()['user']['photos']]==[third,first]
    assert [p['position'] for p in r.json()['user']['photos']]==[0,1]
    assert a.get('/photos/'+second).status_code==404
    for photo_id in (third,first):
        assert a.client.delete('/api/me/photos/'+photo_id).status_code==200
    user=a.get('/me').json()['user']
    assert user['photos']==[] and user['main_photo_url'] is None


def test_upload_and_replace_retry_are_idempotent(students,app):
    a=students['alice']
    key=str(uuid.uuid4())
    body=image_bytes()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[f.result() for f in [pool.submit(upload,a,body,key=key),pool.submit(upload,a,body,key=key)]]
    assert all(r.status_code==200 for r in results)
    photo_id=results[0].json()['photo_id']
    assert results[1].json()['photo_id']==photo_id
    assert len(sql(app,'SELECT id FROM profile_photos'))==1
    assert upload(a,image_bytes('blue'),key=key).status_code==409
    replacement_key=str(uuid.uuid4())
    first=upload(a,image_bytes('green'),photo_id=photo_id,key=replacement_key)
    retried=upload(a,image_bytes('green'),photo_id=photo_id,key=replacement_key)
    assert first.status_code==retried.status_code==200
    assert first.json()['user']['main_photo_url']==retried.json()['user']['main_photo_url']
    assert upload(a,image_bytes('red'),photo_id=photo_id,key=replacement_key).status_code==409


def test_concurrent_uploads_cannot_exceed_four_photos(students,app):
    a=students['alice']
    for color in ('red','blue','green'):
        assert upload(a,image_bytes(color)).status_code==200
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[f.result() for f in [pool.submit(upload,a),pool.submit(upload,a)]]
    assert sorted(r.status_code for r in results)==[200,409]
    assert len(sql(app,'SELECT id FROM profile_photos WHERE user_id=?',(a.id,)))==4
    assert upload(a).status_code==409


def test_only_owner_can_edit_and_reorder_photos(students):
    a,b=students['alice'],students['brian']
    photo_id=upload(a).json()['photo_id']
    assert upload(b,photo_id=photo_id).status_code==404
    assert b.post(f'/me/photos/{photo_id}/main').status_code==404
    assert b.client.delete('/api/me/photos/'+photo_id).status_code==404
    assert b.client.patch('/api/me/photos/order',json={'photo_ids':[photo_id]}).status_code==422
    assert a.client.patch('/api/me/photos/order',json={'photo_ids':[photo_id,photo_id]}).status_code==422
    assert a.client.patch('/api/me/photos/order',json={'photo_ids':[]}).status_code==422
    assert a.get('/me').json()['user']['photos'][0]['id']==photo_id


def test_photo_access_follows_visibility_connections_and_both_direction_blocks(students):
    a,b,c=students['alice'],students['brian'],students['chipo']
    url=upload(a).json()['user']['main_photo_url']
    assert TestClient(a.client.app).get(url).status_code==401
    assert b.client.get(url).status_code==200
    a.patch({'discoverable':False})
    assert b.client.get(url).status_code==404
    a.patch({'discoverable':True})
    accepted(a,b)
    a.patch({'discoverable':False})
    assert b.client.get(url).status_code==200
    assert c.client.get(url).status_code==404
    b.post('/blocks/'+a.id)
    assert b.client.get(url).status_code==404
    assert a.client.get(url).status_code==200
    b.client.delete('/api/blocks/'+a.id)
    assert b.client.get(url).status_code==404


def test_dating_only_photos_require_reciprocal_active_eligibility(students):
    a,b=students['alice'],students['brian']
    a.patch({'friend_goal':False,'study_goal':False,'dating_enabled':True})
    url=upload(a).json()['user']['main_photo_url']
    assert b.client.get(url).status_code==404
    b.patch({'dating_enabled':True})
    assert b.client.get(url).status_code==200
    a.post('/dating/'+b.id+'/like')
    b.post('/dating/'+a.id+'/like')
    b.patch({'dating_genders':['man']})
    assert b.client.get(url).status_code==404
    b.patch({'dating_genders':['woman']})
    assert b.client.get(url).status_code==200
    a.patch({'dating_enabled':False})
    assert b.client.get(url).status_code==404


def test_profile_photos_respect_institution_and_active_account_scope(students,app):
    a,b=students['alice'],students['brian']
    url=upload(a).json()['user']['main_photo_url']
    sql(app,'INSERT INTO institutions VALUES ("other","Another institution")')
    sql(app,'UPDATE users SET institution_id="other" WHERE id=?',(b.id,))
    assert b.client.get(url).status_code==404
    assert b.get('/profiles/'+a.id).status_code==404
    sql(app,'UPDATE users SET institution_id="zut" WHERE id=?',(b.id,))
    sql(app,'UPDATE users SET status="suspended" WHERE id=?',(a.id,))
    assert b.client.get(url).status_code==404


@pytest.mark.parametrize('action',['delete','deactivate'])
def test_account_lifecycle_hides_or_removes_photo_data(students,app,action):
    a,b=students['alice'],students['brian']
    url=upload(a).json()['user']['main_photo_url']
    assert a.post('/account/'+action,{'password':PASSWORD}).status_code==200
    assert b.client.get(url).status_code==404
    rows=sql(app,'SELECT id FROM profile_photos WHERE user_id=?',(a.id,))
    assert len(rows)==(0 if action=='delete' else 1)


@pytest.mark.parametrize('body',[
    b'',b'not an image',b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    image_bytes(size=(100,100)),image_bytes(fmt='GIF'),image_bytes()[:40],
])
def test_invalid_images_are_rejected_without_changing_gallery(students,body):
    a=students['alice']
    result=upload(a,body)
    assert result.status_code==422,result.text
    assert a.get('/me').json()['user']['photos']==[]


def test_animated_and_excessive_dimension_images_are_rejected(students):
    a=students['alice']
    output=BytesIO()
    Image.new('RGB',(300,300),'red').save(output,'PNG',save_all=True,append_images=[Image.new('RGB',(300,300),'blue')],duration=100,loop=0)
    assert upload(a,output.getvalue()).status_code==422
    body=bytearray(image_bytes())
    body[16:24]=struct.pack('>II',50_000,50_000)
    body[29:33]=struct.pack('>I',zlib.crc32(body[12:29]))
    assert upload(a,bytes(body)).status_code==422


def test_upload_limits_streamed_body_and_csrf_are_enforced(students):
    a=students['alice']
    assert a.client.post('/api/me/photos',content=image_bytes(),headers={'X-CSRF-Token':'bad','X-Upload-Id':str(uuid.uuid4())}).status_code==403
    assert TestClient(a.client.app).post('/api/me/photos',content=image_bytes()).status_code==401
    assert a.client.post('/api/me/photos',content=image_bytes()).status_code==422
    assert upload(a,b'x'*(MAX_UPLOAD_BYTES+1)).status_code==413
    result=a.client.post('/api/me/photos',content=iter([b'x'*(4*1024*1024),b'y'*(4*1024*1024+1)]),headers={'X-Upload-Id':str(uuid.uuid4())})
    assert result.status_code==413
    assert a.patch({'bio':'x'*33000}).status_code==413


def test_legacy_database_gains_photo_table_without_losing_accounts(app):
    before=sql(app,'SELECT id,username FROM users ORDER BY id')
    sql(app,'DROP TABLE profile_photos')
    sql(app,'PRAGMA user_version=1')
    create_app(app.state.db_path,testing=True)
    assert sql(app,'SELECT id,username FROM users ORDER BY id')==before
    assert sql(app,'PRAGMA user_version')[0][0]==5
    assert sql(app,'SELECT id FROM profile_photos')==[]
