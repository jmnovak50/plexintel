import logging
import time
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.middleware.sessions import SessionMiddleware

from api.routes import agent_tools
from api.services import agent_auth as auth, mcp_auth
from api.services.agent_tool_service import WatchHistoryResponse
from tests.test_agent_tool_service import FakeConnection


@pytest.fixture
def client():
    app=FastAPI()
    app.include_router(agent_tools.router,prefix='/api/agent')
    with TestClient(app) as client:
        yield client


def validation(username='alice',admin=False,scopes='plexintel.read'):
    return mcp_auth.MCPTokenValidation(mcp_auth.MCPTokenStatus.VALID,
        mcp_auth.MCPAuthContext('jwt',email='fixture@example.invalid',plex_username=username,is_admin=admin),
        claims={'exp':time.time()+300,'scope':scopes})


def payload(username='alice'):
    return WatchHistoryResponse(user=username,engaged_only=False,count=0,results=[])


@pytest.mark.parametrize('path',['/watch-history','/users','/recommendations?user=alice',
    '/recommendations/1/score?user=alice','/search?q=x','/items/1','/recent-additions'])
def test_anonymous_agent_access_is_rejected_before_queries(client,path):
    with patch.object(agent_tools,'get_agent_watch_history') as query:
        response=client.get('/api/agent'+path)
    assert response.status_code==401
    query.assert_not_called()


def test_spoofed_identity_and_network_headers_are_not_credentials(client):
    response=client.get('/api/agent/watch-history',headers={
        'X-OpenWebUI-User-Email':'admin@example.invalid','X-Forwarded-User':'admin',
        'X-Forwarded-For':'127.0.0.1','X-Authentik-Email':'admin@example.invalid'})
    assert response.status_code==401


@pytest.mark.parametrize('status,expected',[
    (mcp_auth.MCPTokenStatus.INVALID,401),(mcp_auth.MCPTokenStatus.EXPIRED,401),
    (mcp_auth.MCPTokenStatus.WRONG_AUDIENCE,401),(mcp_auth.MCPTokenStatus.WRONG_ISSUER,401),
    (mcp_auth.MCPTokenStatus.INSUFFICIENT_SCOPE,403),(mcp_auth.MCPTokenStatus.UNMAPPED_EMAIL,403),
])
def test_invalid_credentials_fail_closed(client,status,expected):
    with patch.object(mcp_auth,'validate_bearer_token',return_value=mcp_auth.MCPTokenValidation(status)):
        response=client.get('/api/agent/watch-history',headers={'Authorization':'Bearer fixture-token'})
    assert response.status_code==expected


def test_ordinary_user_gets_self_and_cannot_escalate_scope(client):
    with patch.object(mcp_auth,'validate_bearer_token',return_value=validation()),patch.object(agent_tools,'get_agent_watch_history',return_value=payload()) as query:
        assert client.get('/api/agent/watch-history',headers={'Authorization':'Bearer fixture'}).status_code==200
        assert query.call_args.kwargs['user']=='alice'
        for params in ({'user':'bob'},{'all_users':True},{'user':'','all_users':True}):
            query.reset_mock()
            response=client.get('/api/agent/watch-history',params=params,headers={'Authorization':'Bearer fixture'})
            assert response.status_code==403
            query.assert_not_called()
        response=client.get('/api/agent/recommendations',params={'user':'bob'},headers={'Authorization':'Bearer fixture'})
        assert response.status_code==403


def test_all_user_scope_is_explicit_and_admin_only(client):
    with patch.object(mcp_auth,'validate_bearer_token',return_value=validation(admin=True)),patch.object(agent_tools,'get_agent_watch_history',return_value=payload(None)) as query:
        assert client.get('/api/agent/watch-history',params={'all_users':True},headers={'Authorization':'Bearer fixture'}).status_code==200
        assert query.call_args.kwargs['user'] is None
        assert client.get('/api/agent/watch-history',params={'all_users':True,'user':'bob'},headers={'Authorization':'Bearer fixture'}).status_code==400


def test_service_requires_scoped_private_file_and_never_uses_identity_headers(client,tmp_path,monkeypatch):
    secret='fixture-read-service-token-'+('x'*32)
    path=tmp_path/'token';path.write_text(secret);path.chmod(0o600)
    monkeypatch.setenv('PLEXINTEL_AGENT_SERVICE_TOKEN_FILE',str(path))
    with patch.object(agent_tools,'get_agent_watch_history',return_value=payload('bob')) as query:
        headers={'Authorization':'Bearer '+secret,'X-OpenWebUI-User-Email':'admin@example.invalid'}
        assert client.get('/api/agent/watch-history',params={'user':'bob'},headers=headers).status_code==403
        query.assert_not_called()
        monkeypatch.setenv('PLEXINTEL_AGENT_SERVICE_SCOPES','plexintel.read plexintel.read_all')
        assert client.get('/api/agent/watch-history',params={'user':'bob'},headers=headers).status_code==200
        assert query.call_args.kwargs['user']=='bob'
        assert client.get('/api/agent/watch-history',headers=headers).status_code==400
        assert client.get('/api/agent/watch-history',params={'all_users':True},headers=headers).status_code==200
        assert client.post('/api/agent/feedback',json={'user':'bob','rating_key':1,'thumb':'up'},headers=headers).status_code==403
    path.chmod(0o644)
    assert client.get('/api/agent/watch-history',headers=headers).status_code==503


def test_ordinary_user_directory_never_runs_global_search(client):
    with patch.object(mcp_auth,'validate_bearer_token',return_value=validation()),patch.object(agent_tools,'list_agent_users') as global_query,patch('api.services.agent_tool_service.get_agent_self_user',return_value={'count':0,'items':[]}) as own:
        response=client.get('/api/agent/users',params={'username':'bob'},headers={'Authorization':'Bearer fixture'})
    assert response.status_code==200
    global_query.assert_not_called()
    own.assert_called_once_with('alice',username='bob',friendly_name=None)


def test_query_errors_return_safe_incident_without_driver_details(client,caplog):
    secret='password=never-log-this SELECT private_table /internal/file'
    with patch.object(mcp_auth,'validate_bearer_token',return_value=validation()),patch.object(agent_tools,'get_agent_watch_history',side_effect=RuntimeError(secret)),caplog.at_level(logging.ERROR):
        response=client.get('/api/agent/watch-history',headers={'Authorization':'Bearer fixture'})
    assert response.status_code==500 and response.json()['detail']['incident']
    assert secret not in response.text and secret not in caplog.text
    assert 'RuntimeError' in caplog.text


def test_history_service_itself_sanitizes_errors(caplog):
    from api.services import agent_tool_service as service
    from fastapi import HTTPException
    with patch.object(service,'connect_db',side_effect=RuntimeError('secret-driver-detail')),caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as raised:
            service.get_agent_watch_history(user='alice')
    assert raised.value.status_code==500
    assert 'secret-driver-detail' not in str(raised.value.detail)+caplog.text


def test_secure_browser_session_uses_database_identity_and_csrf_origin(monkeypatch):
    secret='fixture-session-secret-'+('x'*32)
    monkeypatch.setenv('SESSION_SECRET',secret)
    app=FastAPI();app.add_middleware(SessionMiddleware,secret_key=secret)
    app.state.agent_session_auth_enabled=True
    app.include_router(agent_tools.router,prefix='/api/agent')
    @app.get('/fixture-login')
    def login(request: __import__('fastapi').Request):
        request.session.update(username='alice',user_id=1,plex_token='fixture-proof')
        return {}
    connection=FakeConnection([{'username':'alice','is_admin':False}])
    connection.close=lambda: None
    with TestClient(app) as client,patch.object(auth,'connect_db',return_value=connection),patch.object(agent_tools,'get_agent_watch_history',return_value=payload()):
        client.get('/fixture-login')
        assert client.get('/api/agent/watch-history').status_code==200
        assert client.get('/api/agent/watch-history',params={'user':'bob'}).status_code==403
        assert client.post('/api/agent/feedback',json={'user':'alice','rating_key':1,'thumb':'up'}).status_code==403
        app.state.agent_session_auth_enabled=False
        assert client.get('/api/agent/watch-history').status_code==503


def test_missing_expiration_is_rejected(client):
    token=validation();token.claims.pop('exp')
    with patch.object(mcp_auth,'validate_bearer_token',return_value=token):
        assert client.get('/api/agent/watch-history',headers={'Authorization':'Bearer fixture'}).status_code==401


def test_read_all_jwt_claim_cannot_promote_non_admin(client):
    with patch.object(mcp_auth,'validate_bearer_token',return_value=validation(scopes='plexintel.read plexintel.read_all')):
        assert client.get('/api/agent/watch-history',params={'all_users':True},headers={'Authorization':'Bearer fixture'}).status_code==403
        assert client.get('/api/agent/watch-history',params={'user':'bob'},headers={'Authorization':'Bearer fixture'}).status_code==403


def test_deterministic_adapter_reaches_authenticated_rest_without_identity_headers(client,tmp_path,monkeypatch):
    from openwebui_pipelines.plexintel_recommendation_pipeline import Pipeline
    secret='fixture-service-'+('x'*32)
    path=tmp_path/'token';path.write_text(secret);path.chmod(0o600)
    monkeypatch.setenv('PLEXINTEL_AGENT_SERVICE_TOKEN_FILE',str(path))
    monkeypatch.setenv('PLEXINTEL_AGENT_SERVICE_SCOPES','plexintel.read plexintel.read_all')
    monkeypatch.setenv('PLEXINTEL_API_TOKEN',secret)
    pipe=Pipeline()
    def forward(method,url,**kwargs):
        assert kwargs['headers']=={'Authorization':'Bearer '+secret}
        return client.request(method,'/api/agent/watch-history',params=kwargs.get('params'),headers=kwargs['headers'])
    with patch('requests.request',side_effect=forward),patch.object(agent_tools,'get_agent_watch_history',return_value=payload('bob')) as query:
        result=pipe._plex_get('/api/agent/watch-history',{'user':'bob','limit':1})
    assert result['user']=='bob' and result['results']==[]
    assert query.call_args.kwargs['user']=='bob'
