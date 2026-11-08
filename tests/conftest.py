"""Unit tests must never discover an operator's active production installation."""
import pytest


@pytest.fixture(autouse=True)
def isolated_embedding_installation(monkeypatch,tmp_path):
    from api.embedding_generation import runtime
    monkeypatch.setattr(runtime,'MARKER',tmp_path/'embedding-installation.json')
    monkeypatch.setattr(runtime,'TRANSITION',tmp_path/'embedding-transition.json')
