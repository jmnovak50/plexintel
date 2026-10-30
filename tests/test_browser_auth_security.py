"""Provider account responses must not disclose credentials through logging."""
from unittest.mock import Mock
import pytest
from api.services import plex_service


@pytest.mark.parametrize('kind', ['xml', 'json', 'invalid_json', 'denied'])
def test_account_lookup_never_logs_response_or_credentials(monkeypatch, capsys, kind):
    credential = 'synthetic-account-token-canary'
    response = Mock(status_code=401 if kind == 'denied' else 200)
    response.headers = {'Content-Type': 'application/xml' if kind == 'xml' else 'application/json'}
    response.text = f'<user username="fixture" email="fixture@example.invalid" authToken="{credential}" />'
    response.json.return_value = {'user': {'username': 'fixture', 'email': 'fixture@example.invalid', 'authToken': credential}}
    if kind == 'invalid_json':
        response.json.side_effect = ValueError(credential)
    monkeypatch.setattr(plex_service, '_build_plex_headers', lambda **kw: {'X-Plex-Token': credential})
    monkeypatch.setattr(plex_service.httpx, 'get', lambda *a, **kw: response)
    result = plex_service.get_plex_user_info(credential)
    assert result == (None if kind in ('invalid_json', 'denied') else {'username': 'fixture', 'email': 'fixture@example.invalid'})
    captured = capsys.readouterr()
    assert not captured.out and not captured.err


def test_actual_app_login_issues_secure_cookie_without_real_writer(monkeypatch):
    # Import the actual application but never enter its production lifespan.
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'true')
    from api import main
    from api.routes import auth_routes
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware
    middleware = next(m for m in main.app.user_middleware if m.cls is SessionMiddleware)
    assert middleware.kwargs['https_only'] is True
    monkeypatch.setattr(plex_service, 'poll_plex_pin', lambda _: 'synthetic-plex-token')
    monkeypatch.setattr(auth_routes, 'get_plex_user_info', lambda _: {'username': 'fixture', 'email': 'fixture@example.invalid'})
    writer = Mock(return_value=(7, False))
    monkeypatch.setattr(auth_routes, 'get_or_create_user', writer)
    response = TestClient(main.app, base_url='https://testserver').get('/api/auth/status/7')
    assert response.status_code == 200
    cookie = response.headers['set-cookie'].lower()
    assert '; secure' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie
    writer.assert_called_once()
