import pytest

from app.immich.client import InvalidShareLink
from app.immich.shares import extract_share_key, resolve_share_input


def test_extract_share_key_from_url(settings):
    assert extract_share_key("https://photo.example.com/share/ABC_123-x", settings) == "ABC_123-x"


def test_extract_bare_share_key(settings):
    assert extract_share_key("ABC123", settings) == "ABC123"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/share/ABC123",
        "http://photo.example.com/share/ABC123",
        "https://photo.example.com.evil.test/share/ABC123",
        "https://user:pass@photo.example.com/share/ABC123",
    ],
)
def test_reject_foreign_or_unsafe_share_hosts(settings, url):
    with pytest.raises(InvalidShareLink):
        extract_share_key(url, settings)


def test_requires_exactly_one_share_input(settings):
    with pytest.raises(InvalidShareLink):
        resolve_share_input(share_url=None, share_key=None, settings=settings)
    with pytest.raises(InvalidShareLink):
        resolve_share_input(share_url="https://photo.example.com/share/a", share_key="a", settings=settings)

