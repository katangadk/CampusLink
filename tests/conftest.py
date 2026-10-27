import sqlite3

import pytest
from fastapi.testclient import TestClient

from campuslink.app import create_app
from campuslink.seed import PASSWORD, seed


@pytest.fixture(autouse=True)
def isolated_service_configuration(monkeypatch):
    # Tests must never use the operator's actual mail/provider credentials.
    for name in list(__import__('os').environ):
        if name.startswith(('CAMPUSLINK_SMTP_','CAMPUSLINK_SHEERID_')):
            monkeypatch.delenv(name,raising=False)
    monkeypatch.delenv('CAMPUSLINK_MAIL_TOKEN_SECRET',raising=False)
    monkeypatch.setenv('CAMPUSLINK_MODE','local')
    monkeypatch.setenv('CAMPUSLINK_ELIGIBILITY_MODE','preview')
    monkeypatch.setenv('CAMPUSLINK_REQUIRE_APPROVAL','false')
    monkeypatch.setenv('CAMPUSLINK_VERIFICATION_LIVE','false')


class Student:
    def __init__(self, app, name):
        self.client = TestClient(app)
        result = self.client.post('/api/auth/login',json={'email':f'{name}@campuslink.test','password':PASSWORD})
        assert result.status_code==200,result.text
        self.user = result.json()['user']
        self.id = self.user['id']
        self.client.headers['X-CSRF-Token'] = result.json()['csrf']

    def get(self, path, **kwargs):
        return self.client.get('/api'+path,**kwargs)

    def post(self, path, data=None, **kwargs):
        return self.client.post('/api'+path,json=data or {},**kwargs)

    def patch(self, data):
        return self.client.patch('/api/me',json=data)


@pytest.fixture
def app(tmp_path):
    path = tmp_path/'test.sqlite3'
    seed(path)
    return create_app(path,testing=True)


@pytest.fixture
def students(app):
    return {name:Student(app,name) for name in ('alice','brian','chipo','moderator')}


def accepted(a,b,kind='friend'):
    response = a.post('/connections',{'target_id':b.id,'kind':kind})
    assert response.status_code==200,response.text
    rid=response.json()['id']
    response=b.post(f'/connections/{rid}/accept')
    assert response.status_code==200,response.text
    return rid


def sql(app, query, params=()):
    with sqlite3.connect(app.state.db_path) as con:
        con.row_factory=sqlite3.Row
        result=con.execute(query,params).fetchall()
        con.commit()
        return result
