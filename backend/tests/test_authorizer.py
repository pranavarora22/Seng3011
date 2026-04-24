"""Tests for authorizer_lambda: JWT validation for API Gateway."""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

import jwt  # noqa: E402

JWT_SECRET = "test-secret-for-unit-tests"
JWT_ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(token_type="access", expired=False, secret=JWT_SECRET,
                user_id="uid-1", email="user@example.com"):
    if expired:
        exp = datetime.now(timezone.utc) - timedelta(seconds=10)
    else:
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": user_id,
        "email": email,
        "type": token_type,
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _make_event(auth_header=None):
    headers = {}
    if auth_header is not None:
        headers["authorization"] = auth_header
    return {"headers": headers}


def _call(auth_header=None):
    from authorizer_lambda import lambda_handler
    return lambda_handler(_make_event(auth_header), None)


# ---------------------------------------------------------------------------
# Valid token tests
# ---------------------------------------------------------------------------

class TestValidToken(unittest.TestCase):
    def test_valid_access_token_is_authorized(self):
        token = _make_token()
        result = _call(f"Bearer {token}")
        self.assertTrue(result["isAuthorized"])

    def test_valid_token_returns_user_id_in_context(self):
        token = _make_token(user_id="uid-abc")
        result = _call(f"Bearer {token}")
        self.assertEqual(result["context"]["user_id"], "uid-abc")

    def test_valid_token_returns_email_in_context(self):
        token = _make_token(email="alice@example.com")
        result = _call(f"Bearer {token}")
        self.assertEqual(result["context"]["email"], "alice@example.com")

    def test_valid_token_context_has_both_fields(self):
        token = _make_token(user_id="u1", email="b@c.com")
        result = _call(f"Bearer {token}")
        self.assertIn("user_id", result["context"])
        self.assertIn("email", result["context"])


# ---------------------------------------------------------------------------
# Missing / malformed header tests
# ---------------------------------------------------------------------------

class TestMissingOrMalformedHeader(unittest.TestCase):
    def test_no_authorization_header_is_not_authorized(self):
        result = _call(auth_header=None)
        self.assertFalse(result["isAuthorized"])

    def test_empty_authorization_header_is_not_authorized(self):
        result = _call(auth_header="")
        self.assertFalse(result["isAuthorized"])

    def test_missing_bearer_prefix_is_not_authorized(self):
        token = _make_token()
        result = _call(auth_header=token)  # no "Bearer " prefix
        self.assertFalse(result["isAuthorized"])

    def test_basic_prefix_is_not_authorized(self):
        token = _make_token()
        result = _call(auth_header=f"Basic {token}")
        self.assertFalse(result["isAuthorized"])

    def test_token_prefix_only_no_value_is_not_authorized(self):
        result = _call(auth_header="Bearer ")
        self.assertFalse(result["isAuthorized"])

    def test_bearer_lowercase_is_not_authorized(self):
        """Header matching is case-sensitive for 'Bearer' scheme per RFC 6750."""
        token = _make_token()
        result = _call(auth_header=f"bearer {token}")
        self.assertFalse(result["isAuthorized"])

    def test_no_headers_key_in_event_is_not_authorized(self):
        from authorizer_lambda import lambda_handler
        result = lambda_handler({}, None)
        self.assertFalse(result["isAuthorized"])

    def test_none_headers_value_is_not_authorized(self):
        from authorizer_lambda import lambda_handler
        result = lambda_handler({"headers": None}, None)
        self.assertFalse(result["isAuthorized"])


# ---------------------------------------------------------------------------
# Invalid / tampered token tests
# ---------------------------------------------------------------------------

class TestInvalidToken(unittest.TestCase):
    def test_wrong_secret_is_not_authorized(self):
        token = _make_token(secret="wrong-secret")
        result = _call(f"Bearer {token}")
        self.assertFalse(result["isAuthorized"])

    def test_expired_token_is_not_authorized(self):
        token = _make_token(expired=True)
        result = _call(f"Bearer {token}")
        self.assertFalse(result["isAuthorized"])

    def test_malformed_token_is_not_authorized(self):
        result = _call("Bearer this.is.notjwt")
        self.assertFalse(result["isAuthorized"])

    def test_garbage_string_is_not_authorized(self):
        result = _call("Bearer not-a-token-at-all")
        self.assertFalse(result["isAuthorized"])

    def test_truncated_token_is_not_authorized(self):
        token = _make_token()
        truncated = token[:len(token) // 2]
        result = _call(f"Bearer {truncated}")
        self.assertFalse(result["isAuthorized"])

    def test_tampered_payload_is_not_authorized(self):
        """Changing the payload segment invalidates the signature."""
        import base64
        token = _make_token()
        parts = token.split(".")
        # Tamper with payload: decode, change email, re-encode without re-signing
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        tampered = payload_bytes.replace(b"user@example.com", b"hacker@evil.com")
        parts[1] = base64.urlsafe_b64encode(tampered).rstrip(b"=").decode()
        tampered_token = ".".join(parts)
        result = _call(f"Bearer {tampered_token}")
        self.assertFalse(result["isAuthorized"])

    def test_none_algorithm_token_is_not_authorized(self):
        """Tokens signed with 'none' algorithm must be rejected."""
        # Manually construct a none-alg token
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
        payload_data = '{"sub":"uid","email":"x@y.com","type":"access","exp":9999999999,"iat":0}'
        payload_enc = base64.urlsafe_b64encode(payload_data.encode()).rstrip(b"=").decode()
        none_token = f"{header}.{payload_enc}."
        result = _call(f"Bearer {none_token}")
        self.assertFalse(result["isAuthorized"])


# ---------------------------------------------------------------------------
# Wrong token type tests
# ---------------------------------------------------------------------------

class TestWrongTokenType(unittest.TestCase):
    def test_refresh_token_is_not_authorized(self):
        """A refresh token must not be accepted as an access token."""
        token = _make_token(token_type="refresh")
        result = _call(f"Bearer {token}")
        self.assertFalse(result["isAuthorized"])

    def test_unknown_token_type_is_not_authorized(self):
        token = _make_token(token_type="unknown")
        result = _call(f"Bearer {token}")
        self.assertFalse(result["isAuthorized"])

    def test_missing_type_claim_is_not_authorized(self):
        payload = {
            "sub": "uid",
            "email": "x@y.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            # no "type" field
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        result = _call(f"Bearer {token}")
        self.assertFalse(result["isAuthorized"])


# ---------------------------------------------------------------------------
# Response shape tests
# ---------------------------------------------------------------------------

class TestResponseShape(unittest.TestCase):
    def test_authorized_result_always_has_is_authorized_key(self):
        token = _make_token()
        result = _call(f"Bearer {token}")
        self.assertIn("isAuthorized", result)

    def test_unauthorized_result_always_has_is_authorized_key(self):
        result = _call(auth_header=None)
        self.assertIn("isAuthorized", result)

    def test_unauthorized_result_has_no_context(self):
        result = _call(auth_header=None)
        self.assertNotIn("context", result)

    def test_authorized_result_context_is_dict(self):
        token = _make_token()
        result = _call(f"Bearer {token}")
        self.assertIsInstance(result["context"], dict)

    def test_multiple_valid_calls_all_authorized(self):
        """Authorizer is stateless — repeated calls with same valid token always succeed."""
        token = _make_token()
        for _ in range(5):
            result = _call(f"Bearer {token}")
            self.assertTrue(result["isAuthorized"])

    def test_multiple_invalid_calls_all_unauthorized(self):
        for _ in range(5):
            result = _call("Bearer bad-token")
            self.assertFalse(result["isAuthorized"])


if __name__ == "__main__":
    unittest.main()
