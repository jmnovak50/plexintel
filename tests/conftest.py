"""Unit tests must never discover an operator's active production installation."""
import pytest


@pytest.fixture(autouse=True)
def forbid_unmocked_poster_settings_persistence(monkeypatch):
    """Discovery fixtures must never write into an operator's app_settings."""
    from api.services import poster_service
    def forbidden(identifier):
        raise AssertionError('Mock persist_plex_server_identifier explicitly; fixture settings must not reach a database')
    monkeypatch.setattr(poster_service,'persist_plex_server_identifier',forbidden)


@pytest.fixture(autouse=True)
def isolated_embedding_installation(monkeypatch,tmp_path):
    from api.embedding_generation import runtime
    monkeypatch.setattr(runtime,'MARKER',tmp_path/'embedding-installation.json')
    monkeypatch.setattr(runtime,'TRANSITION',tmp_path/'embedding-transition.json')
