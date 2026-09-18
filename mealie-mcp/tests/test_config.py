from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def _values(settings, **updates):
    values = settings.model_dump()
    values.update(updates)
    return values


def test_account_scopes_use_whitespace_string_without_json_parsing(settings):
    configured = Settings.model_validate(_values(settings, account_oidc_scopes="openid   profile email"))
    assert configured.account_scopes == ["openid", "profile", "email"]


@pytest.mark.parametrize(
    "updates",
    [
        {"account_session_secret": "too-short"},
        {"account_oidc_scopes": "profile email"},
        {"environment": "production", "account_cookie_secure": False},
        {
            "environment": "production",
            "account_public_url": "http://mcp.example.com/account",
            "account_redirect_uri": "http://mcp.example.com/account/callback",
        },
    ],
)
def test_account_security_configuration_is_validated(settings, updates):
    with pytest.raises(ValidationError):
        Settings.model_validate(_values(settings, **updates))
