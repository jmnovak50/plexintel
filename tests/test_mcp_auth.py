from __future__ import annotations

import json
import time
import unittest
from io import BytesIO
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.services import mcp_auth


class MCPAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()
        cls.public_pem = cls.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        cls.issuer = "https://auth.kabolly.com/application/o/plexintel-chatgpt/"
        cls.oauth_settings = mcp_auth.MCPOAuthSettings(
            issuer_url=cls.issuer,
            audience="https://plexintel.kabolly.com/mcp",
            email_claim="email",
            resource_url="https://plexintel.kabolly.com/mcp",
            required_scopes=("plexintel.read",),
        )

    def setUp(self):
        mcp_auth.reset_jwks_cache()

    def _encode_token(
        self,
        claims: dict,
        *,
        expired: bool = False,
        include_audience: bool = True,
    ) -> str:
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": "user-1",
            "iat": now,
            "exp": now - 60 if expired else now + 3600,
            "aud": "https://plexintel.kabolly.com/mcp",
            "scope": "openid email plexintel.read",
            **claims,
        }
        if not include_audience:
            payload.pop("aud", None)
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "plexintel-test-key"},
        )

    def _validate(self, token: str):
        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            return mcp_auth.validate_bearer_token(token, self.oauth_settings)

    def test_extract_email_from_claims_prefers_configured_claim(self):
        claims = {"email": "jason@sheffieldave.com", "preferred_username": "other@example.com"}

        email = mcp_auth.extract_email_from_claims(claims, "email")

        self.assertEqual(email, "jason@sheffieldave.com")

    def test_extract_email_from_claims_falls_back_to_preferred_username(self):
        claims = {"preferred_username": "jason@sheffieldave.com"}

        email = mcp_auth.extract_email_from_claims(claims, "missing")

        self.assertEqual(email, "jason@sheffieldave.com")

    def test_authenticate_bearer_token_maps_email_to_plex_user(self):
        token = self._encode_token({"email": "jason@sheffieldave.com"})
        fake_user = {
            "user_id": 7,
            "username": "jmnovak",
            "plex_email": "jason@sheffieldave.com",
            "is_admin": False,
        }

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            with patch.object(mcp_auth, "get_user_by_email", return_value=fake_user):
                context = mcp_auth.authenticate_bearer_token(token, self.oauth_settings)

        self.assertIsNotNone(context)
        self.assertEqual(context.auth_method, "jwt")
        self.assertEqual(context.email, "jason@sheffieldave.com")
        self.assertEqual(context.plex_username, "jmnovak")
        self.assertEqual(context.user_id, 7)

    def test_validate_bearer_token_accepts_exact_expected_claims_and_scope(self):
        token = self._encode_token({"email": "mapped@example.com"})
        fake_user = {
            "user_id": 7,
            "username": "mapped-user",
            "is_admin": False,
        }

        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            with patch.object(mcp_auth, "get_user_by_email", return_value=fake_user):
                result = mcp_auth.validate_bearer_token(token, self.oauth_settings)

        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.VALID)
        self.assertEqual(result.context.plex_username, "mapped-user")

    def test_validate_bearer_token_rejects_missing_audience(self):
        token = self._encode_token(
            {"email": "user@example.com"},
            include_audience=False,
        )

        with self.assertLogs(mcp_auth.logger, level="INFO") as captured:
            result = self._validate(token)

        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.INVALID)
        diagnostics = "\n".join(captured.output)
        self.assertIn("stage=signature_and_registered_claims", diagnostics)
        self.assertIn("exception_class=MissingRequiredClaimError", diagnostics)
        self.assertIn("aud=None", diagnostics)
        self.assertNotIn(token, diagnostics)

    def test_validate_bearer_token_rejects_incorrect_audience(self):
        token = self._encode_token(
            {"aud": "https://unrelated.example/resource", "email": "user@example.com"}
        )

        result = self._validate(token)

        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.WRONG_AUDIENCE)

    def test_validate_bearer_token_rejects_missing_required_scope(self):
        token = self._encode_token({"scope": "openid email", "email": "user@example.com"})

        result = self._validate(token)

        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.INSUFFICIENT_SCOPE)

    def test_validate_bearer_token_rejects_expired_token(self):
        token = self._encode_token({"email": "user@example.com"}, expired=True)

        result = self._validate(token)

        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.EXPIRED)

    def test_validation_failure_diagnostics_are_specific_and_do_not_leak_token_or_identity(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time.time())
        token = jwt.encode(
            {
                "iss": self.issuer,
                "sub": "sensitive-subject",
                "email": "private-person@example.com",
                "aud": "https://plexintel.kabolly.com/mcp",
                "exp": now + 3600,
                "nbf": now - 60,
                "scope": "openid email plexintel.read",
                "scp": ["plexintel.read"],
            },
            other_key,
            algorithm="RS256",
            headers={"kid": "authentik-signing-key"},
        )

        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            with self.assertLogs(mcp_auth.logger, level="INFO") as captured:
                result = mcp_auth.validate_bearer_token(token, self.oauth_settings)

        diagnostics = "\n".join(captured.output)
        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.INVALID)
        self.assertIn("stage=signature_and_registered_claims", diagnostics)
        self.assertIn("exception_class=InvalidSignatureError", diagnostics)
        self.assertIn("alg=RS256", diagnostics)
        self.assertIn("kid=authentik-signing-key", diagnostics)
        self.assertIn(f"iss={self.issuer}", diagnostics)
        self.assertIn("aud=https://plexintel.kabolly.com/mcp", diagnostics)
        self.assertIn("scope=openid email plexintel.read", diagnostics)
        self.assertIn("required_scopes=('plexintel.read',)", diagnostics)
        self.assertIn("'email': True", diagnostics)
        self.assertNotIn(token, diagnostics)
        self.assertNotIn(token.rsplit(".", 1)[1], diagnostics)
        self.assertNotIn("private-person@example.com", diagnostics)
        self.assertNotIn("sensitive-subject", diagnostics)

    def test_authenticate_bearer_token_returns_email_only_when_user_not_mapped(self):
        token = self._encode_token({"email": "unknown@example.com"})

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            with patch.object(mcp_auth, "get_user_by_email", return_value=None):
                context = mcp_auth.authenticate_bearer_token(token, self.oauth_settings)

        self.assertIsNotNone(context)
        self.assertEqual(context.email, "unknown@example.com")
        self.assertIsNone(context.plex_username)

    def test_authenticate_bearer_token_rejects_invalid_signature(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            {
                "iss": self.issuer,
                "email": "jason@sheffieldave.com",
                "exp": int(time.time()) + 3600,
            },
            other_key,
            algorithm="RS256",
        )

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            context = mcp_auth.authenticate_bearer_token(token, self.oauth_settings)

        self.assertIsNone(context)

    def test_authenticate_bearer_token_rejects_expired_token(self):
        token = self._encode_token({"email": "jason@sheffieldave.com"}, expired=True)

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            context = mcp_auth.authenticate_bearer_token(token, self.oauth_settings)

        self.assertIsNone(context)

    def test_authenticate_bearer_token_validates_audience_when_configured(self):
        settings = mcp_auth.MCPOAuthSettings(
            issuer_url=self.issuer,
            audience="openwebui-client-id",
            email_claim="email",
            resource_url="https://plexintel.kabolly.com/mcp",
            required_scopes=("plexintel.read",),
        )
        token = self._encode_token({"email": "jason@sheffieldave.com", "aud": "wrong-audience"})

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            context = mcp_auth.authenticate_bearer_token(token, settings)

        self.assertIsNone(context)

    def test_decode_jwt_accepts_exact_issuer_with_trailing_slash(self):
        settings = mcp_auth.MCPOAuthSettings(
            issuer_url=self.issuer,
            audience="https://plexintel.kabolly.com/mcp",
            email_claim="email",
            resource_url="https://plexintel.kabolly.com/mcp",
            required_scopes=("plexintel.read",),
        )
        token = self._encode_token({"email": "jason@sheffieldave.com"})

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            claims = mcp_auth._decode_jwt(token, settings)

        self.assertEqual(claims["email"], "jason@sheffieldave.com")

    def test_validate_bearer_token_rejects_issuer_missing_trailing_slash(self):
        token = self._encode_token(
            {
                "iss": "https://auth.kabolly.com/application/o/plexintel-chatgpt",
                "email": "jason@sheffieldave.com",
            }
        )

        with patch.object(mcp_auth, "_get_signing_key") as mock_signing_key:
            mock_signing_key.return_value.key = self.public_pem
            result = mcp_auth.validate_bearer_token(token, self.oauth_settings)

        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.WRONG_ISSUER)

    def test_validate_bearer_token_reports_wrong_issuer(self):
        token = self._encode_token({"iss": "https://issuer.example/wrong", "email": "user@example.com"})
        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            result = mcp_auth.validate_bearer_token(token, self.oauth_settings)
        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.WRONG_ISSUER)

    def test_validate_bearer_token_reports_not_yet_valid(self):
        token = self._encode_token({"nbf": int(time.time()) + 600, "email": "user@example.com"})
        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            result = mcp_auth.validate_bearer_token(token, self.oauth_settings)
        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.NOT_YET_VALID)

    def test_validate_bearer_token_requires_all_scopes(self):
        token = self._encode_token({"scope": "openid email", "email": "user@example.com"})
        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            result = mcp_auth.validate_bearer_token(token, self.oauth_settings)
        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.INSUFFICIENT_SCOPE)

    def test_validate_bearer_token_accepts_audience_and_scp_arrays(self):
        token = self._encode_token(
            {
                "aud": ["another-resource", "https://plexintel.kabolly.com/mcp"],
                "scope": None,
                "scp": ["openid", "plexintel.read"],
                "email": "user@example.com",
            }
        )
        with patch.object(mcp_auth, "_get_signing_key") as signing_key:
            signing_key.return_value.key = self.public_pem
            with patch.object(mcp_auth, "get_user_by_email", return_value=None):
                result = mcp_auth.validate_bearer_token(token, self.oauth_settings)
        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.UNMAPPED_EMAIL)

    def test_get_settings_preserves_issuer_slash_and_slashless_audience(self):
        values = {
            "mcp.oauth.issuer_url": "  https://auth.kabolly.com/application/o/plexintel-chatgpt/  ",
            "mcp.oauth.audience": "https://plexintel.kabolly.com/mcp",
            "mcp.oauth.email_claim": "email",
            "mcp.oauth.resource_url": "https://plexintel.kabolly.com/mcp",
            "mcp.oauth.required_scopes": "plexintel.read",
        }
        with patch.object(mcp_auth, "get_setting_value", side_effect=lambda key, default=None: values.get(key, default)):
            settings = mcp_auth.get_mcp_oauth_settings()

        self.assertEqual(settings.issuer_url, self.issuer)
        self.assertEqual(settings.audience, "https://plexintel.kabolly.com/mcp")
        self.assertEqual(settings.resource_url, "https://plexintel.kabolly.com/mcp")

    def test_discovery_url_handles_trailing_issuer_slash(self):
        with patch.object(mcp_auth.httpx, "Client") as client_class:
            client = client_class.return_value.__enter__.return_value
            client.get.return_value.json.return_value = {
                "jwks_uri": "https://auth.kabolly.com/application/o/plexintel-chatgpt/jwks/"
            }

            jwks_uri = mcp_auth._fetch_jwks_uri(self.issuer)

        client.get.assert_called_once_with(
            "https://auth.kabolly.com/application/o/plexintel-chatgpt/.well-known/openid-configuration"
        )
        self.assertEqual(jwks_uri, "https://auth.kabolly.com/application/o/plexintel-chatgpt/jwks/")

    def test_jwks_request_headers_and_timeout_continue_through_full_validation(self):
        token = self._encode_token({"email": "mapped@example.com"})
        public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.public_key))
        public_jwk["kid"] = "plexintel-test-key"
        jwks_response = {"keys": [public_jwk]}
        captured_request = {}

        def urlopen(request, *, timeout, context):
            captured_request["request"] = request
            captured_request["timeout"] = timeout
            captured_request["context"] = context
            return BytesIO(json.dumps(jwks_response).encode("utf-8"))

        fake_user = {
            "user_id": 7,
            "username": "mapped-user",
            "is_admin": False,
        }
        with patch.object(
            mcp_auth,
            "_fetch_jwks_uri",
            return_value="https://auth.kabolly.com/application/o/plexintel-chatgpt/jwks/",
        ):
            with patch("jwt.jwks_client.urllib.request.urlopen", side_effect=urlopen) as fetch:
                with patch.object(mcp_auth, "get_user_by_email", return_value=fake_user):
                    result = mcp_auth.validate_bearer_token(token, self.oauth_settings)

        request = captured_request["request"]
        self.assertEqual(result.status, mcp_auth.MCPTokenStatus.VALID)
        self.assertEqual(result.context.plex_username, "mapped-user")
        self.assertEqual(request.full_url, "https://auth.kabolly.com/application/o/plexintel-chatgpt/jwks/")
        self.assertEqual(request.get_header("User-agent"), "PlexIntel/1.0")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(captured_request["timeout"], 10)
        self.assertIsNone(captured_request["context"])
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
