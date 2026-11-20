from types import SimpleNamespace
from unittest.mock import Mock,MagicMock
import pytest
from api.services import poster_service
from api.services.poster_service import persist_plex_server_identifier as actual_persist


def test_unmocked_discovery_cannot_persist_fixture_into_operator_settings(monkeypatch):
    poster_service.fetch_tautulli_server_identifier.cache_clear()
    monkeypatch.setattr(poster_service,'get_setting_value',lambda key,default=None:{
        'tautulli.api_url':'https://tautulli.invalid/api','tautulli.api_key':'fictional'}.get(key,default))
    monkeypatch.setattr(poster_service.requests,'get',Mock(return_value=SimpleNamespace(
        raise_for_status=lambda:None,json=lambda:{'response':{'data':{'pms_identifier':'real-machine-id'}}})))
    database=Mock(side_effect=AssertionError('No database access allowed'))
    monkeypatch.setattr(poster_service,'connect_db',database)
    with pytest.raises(AssertionError,match='Mock persist_plex_server_identifier explicitly'):
        poster_service.fetch_tautulli_server_identifier()
    database.assert_not_called()
    poster_service.fetch_tautulli_server_identifier.cache_clear()


def test_explicit_persistence_test_uses_only_a_fake_connection(monkeypatch):
    conn=MagicMock();connect=Mock(return_value=conn)
    monkeypatch.setattr(poster_service,'connect_db',connect)
    monkeypatch.setattr(poster_service,'ensure_settings_schema',Mock())
    actual_persist('isolated-test-machine')
    connect.assert_called_once_with();conn.commit.assert_called_once_with()
    values=conn.cursor.return_value.__enter__.return_value.execute.call_args.args[1]
    assert values[0]=='plex.server_identifier' and values[1]=='isolated-test-machine'
