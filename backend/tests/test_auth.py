"""Tests for auth_lambda: signup, login, refresh, routing, and security edge cases."""

import json
import os
import sys
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set env vars before the module is imported.
# Dummy AWS credentials prevent NoRegionError when boto3.resource() is called at
# module level; the dynamodb object is replaced by a Mock in every test anyway.
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("USERS_TABLE", "seng3011-users-test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

import jwt  # noqa: E402
import bcrypt  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JWT_SECRET = "test-secret-for-unit-tests"
JWT_ALGORITHM = "HS256"


def _make_event(method, path, body=None):
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "body": json.dumps(body) if body is not None else None,
    }


def _make_user_item(email="test@example.com", password="Password1"):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return {
        "email": email,
        "user_id": "user-uuid-123",
        "name": "Test User",
        "password_hash": hashed,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def _make_refresh_token(user_id="uid", email="test@example.com", expired=False):
    if expired:
        exp = datetime.now(timezone.utc) - timedelta(seconds=1)
    else:
        exp = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode(
        {"sub": user_id, "email": email, "type": "refresh", "exp": exp,
         "iat": datetime.now(timezone.utc)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def _make_access_token(user_id="uid", email="test@example.com"):
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "type": "access", "exp": exp,
         "iat": datetime.now(timezone.utc)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def _mock_table(get_item_return=None, put_item_return=None):
    table = MagicMock()
    table.get_item.return_value = get_item_return or {}
    table.put_item.return_value = put_item_return or {}
    return table


# ---------------------------------------------------------------------------
# Signup tests
# ---------------------------------------------------------------------------

class TestSignup(unittest.TestCase):
    def setUp(self):
        import auth_lambda
        self._patcher = patch("auth_lambda.dynamodb")
        self.mock_dynamodb = self._patcher.start()
        self.handler = auth_lambda.lambda_handler

    def tearDown(self):
        self._patcher.stop()

    def _call(self, body):
        table = _mock_table(get_item_return={})  # no existing user
        self.mock_dynamodb.Table.return_value = table
        return self.handler(_make_event("POST", "/auth/signup", body), None), table

    # --- happy path ---

    def test_signup_returns_201(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1", "name": "Alice"})
        self.assertEqual(result["statusCode"], 201)

    def test_signup_returns_access_and_refresh_tokens(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1"})
        body = json.loads(result["body"])
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["token_type"], "Bearer")

    def test_signup_returns_user_object(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1", "name": "Alice"})
        body = json.loads(result["body"])
        self.assertEqual(body["user"]["email"], "new@example.com")
        self.assertEqual(body["user"]["name"], "Alice")
        self.assertIn("id", body["user"])

    def test_signup_password_not_in_response(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1"})
        self.assertNotIn("Password1", result["body"])
        self.assertNotIn("password", json.loads(result["body"]).get("user", {}))

    def test_signup_email_normalised_to_lowercase(self):
        result, _ = self._call({"email": "UPPER@EXAMPLE.COM", "password": "Password1"})
        body = json.loads(result["body"])
        self.assertEqual(body["user"]["email"], "upper@example.com")

    def test_signup_name_is_optional(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1"})
        self.assertEqual(result["statusCode"], 201)

    def test_signup_stores_hashed_password_in_dynamo(self):
        _, table = self._call({"email": "new@example.com", "password": "Password1"})
        call_args = table.put_item.call_args[1]["Item"]
        self.assertIn("password_hash", call_args)
        self.assertNotEqual(call_args["password_hash"], "Password1")
        # Verify it's a real bcrypt hash
        self.assertTrue(bcrypt.checkpw(b"Password1", call_args["password_hash"].encode()))

    def test_signup_access_token_is_valid_jwt(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1"})
        token = json.loads(result["body"])["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertEqual(payload["type"], "access")
        self.assertEqual(payload["email"], "new@example.com")

    def test_signup_refresh_token_has_correct_type(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1"})
        token = json.loads(result["body"])["refresh_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertEqual(payload["type"], "refresh")

    def test_signup_dynamo_put_item_called_once(self):
        _, table = self._call({"email": "new@example.com", "password": "Password1"})
        table.put_item.assert_called_once()

    # --- missing fields ---

    def test_signup_missing_email_returns_400(self):
        result, _ = self._call({"password": "Password1"})
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("Email and password", json.loads(result["body"])["error"])

    def test_signup_missing_password_returns_400(self):
        result, _ = self._call({"email": "new@example.com"})
        self.assertEqual(result["statusCode"], 400)

    def test_signup_empty_body_returns_400(self):
        result, _ = self._call({})
        self.assertEqual(result["statusCode"], 400)

    def test_signup_empty_email_returns_400(self):
        result, _ = self._call({"email": "", "password": "Password1"})
        self.assertEqual(result["statusCode"], 400)

    def test_signup_empty_password_returns_400(self):
        result, _ = self._call({"email": "new@example.com", "password": ""})
        self.assertEqual(result["statusCode"], 400)

    # --- email validation ---

    def test_signup_email_missing_at_returns_400(self):
        result, _ = self._call({"email": "notanemail", "password": "Password1"})
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("email", json.loads(result["body"])["error"].lower())

    def test_signup_email_missing_domain_dot_returns_400(self):
        result, _ = self._call({"email": "user@nodot", "password": "Password1"})
        self.assertEqual(result["statusCode"], 400)

    def test_signup_email_double_at_returns_400(self):
        result, _ = self._call({"email": "user@@example.com", "password": "Password1"})
        self.assertEqual(result["statusCode"], 400)

    # --- password policy ---

    def test_signup_short_password_returns_400(self):
        result, _ = self._call({"email": "new@example.com", "password": "Abc1"})
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("8", json.loads(result["body"])["error"])

    def test_signup_password_no_uppercase_returns_400(self):
        result, _ = self._call({"email": "new@example.com", "password": "alllower1"})
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("uppercase", json.loads(result["body"])["error"])

    def test_signup_password_no_digit_returns_400(self):
        result, _ = self._call({"email": "new@example.com", "password": "NoDigitHere"})
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("number", json.loads(result["body"])["error"])

    def test_signup_password_exactly_8_chars_valid(self):
        result, _ = self._call({"email": "new@example.com", "password": "Passw0rd"})
        self.assertEqual(result["statusCode"], 201)

    # --- duplicate user ---

    def test_signup_duplicate_email_returns_409(self):
        import auth_lambda
        existing_item = _make_user_item("dup@example.com")
        table = _mock_table(get_item_return={"Item": existing_item})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/signup", {"email": "dup@example.com", "password": "Password1"}),
            None,
        )
        self.assertEqual(result["statusCode"], 409)
        self.assertIn("already", json.loads(result["body"])["error"].lower())

    def test_signup_duplicate_email_does_not_overwrite(self):
        import auth_lambda
        existing_item = _make_user_item("dup@example.com")
        table = _mock_table(get_item_return={"Item": existing_item})
        self.mock_dynamodb.Table.return_value = table
        self.handler(
            _make_event("POST", "/auth/signup", {"email": "dup@example.com", "password": "Password1"}),
            None,
        )
        table.put_item.assert_not_called()

    # --- CORS ---

    def test_signup_response_has_cors_headers(self):
        result, _ = self._call({"email": "new@example.com", "password": "Password1"})
        self.assertIn("Access-Control-Allow-Origin", result["headers"])


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

class TestLogin(unittest.TestCase):
    def setUp(self):
        self._patcher = patch("auth_lambda.dynamodb")
        self.mock_dynamodb = self._patcher.start()
        import auth_lambda
        self.handler = auth_lambda.lambda_handler

    def tearDown(self):
        self._patcher.stop()

    def _call_with_user(self, email="test@example.com", password="Password1", stored_password="Password1"):
        item = _make_user_item(email=email, password=stored_password)
        table = _mock_table(get_item_return={"Item": item})
        self.mock_dynamodb.Table.return_value = table
        return self.handler(_make_event("POST", "/auth/login", {"email": email, "password": password}), None)

    def _call_no_user(self, email="ghost@example.com", password="Password1"):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        return self.handler(_make_event("POST", "/auth/login", {"email": email, "password": password}), None)

    # --- happy path ---

    def test_login_returns_200(self):
        result = self._call_with_user()
        self.assertEqual(result["statusCode"], 200)

    def test_login_returns_tokens(self):
        result = self._call_with_user()
        body = json.loads(result["body"])
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)

    def test_login_returns_user_object(self):
        result = self._call_with_user(email="test@example.com")
        body = json.loads(result["body"])
        self.assertEqual(body["user"]["email"], "test@example.com")
        self.assertIn("id", body["user"])

    def test_login_access_token_valid_jwt(self):
        result = self._call_with_user()
        token = json.loads(result["body"])["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertEqual(payload["type"], "access")

    def test_login_email_case_insensitive(self):
        # Stored as lowercase; login with uppercase should succeed
        item = _make_user_item(email="test@example.com")
        table = _mock_table(get_item_return={"Item": item})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/login", {"email": "TEST@EXAMPLE.COM", "password": "Password1"}),
            None,
        )
        self.assertEqual(result["statusCode"], 200)

    # --- wrong credentials ---

    def test_login_wrong_password_returns_401(self):
        result = self._call_with_user(password="WrongPass1")
        self.assertEqual(result["statusCode"], 401)

    def test_login_unknown_email_returns_401(self):
        result = self._call_no_user()
        self.assertEqual(result["statusCode"], 401)

    def test_login_wrong_email_same_message_as_wrong_password(self):
        """Error message must be identical for wrong email vs wrong password (prevent enumeration)."""
        result_wrong_email = self._call_no_user(email="nobody@example.com")
        result_wrong_pass = self._call_with_user(password="WrongPass1")
        body_email = json.loads(result_wrong_email["body"])
        body_pass = json.loads(result_wrong_pass["body"])
        self.assertEqual(body_email["error"], body_pass["error"])

    def test_login_wrong_password_no_tokens_in_response(self):
        result = self._call_with_user(password="WrongPass1")
        body = json.loads(result["body"])
        self.assertNotIn("access_token", body)
        self.assertNotIn("refresh_token", body)

    # --- missing fields ---

    def test_login_missing_email_returns_400(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(_make_event("POST", "/auth/login", {"password": "Password1"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_login_missing_password_returns_400(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(_make_event("POST", "/auth/login", {"email": "test@example.com"}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_login_empty_body_returns_400(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(_make_event("POST", "/auth/login", {}), None)
        self.assertEqual(result["statusCode"], 400)

    # --- CORS ---

    def test_login_response_has_cors_headers(self):
        result = self._call_with_user()
        self.assertIn("Access-Control-Allow-Origin", result["headers"])


# ---------------------------------------------------------------------------
# Refresh token tests
# ---------------------------------------------------------------------------

class TestRefresh(unittest.TestCase):
    def setUp(self):
        self._patcher = patch("auth_lambda.dynamodb")
        self.mock_dynamodb = self._patcher.start()
        import auth_lambda
        self.handler = auth_lambda.lambda_handler

    def tearDown(self):
        self._patcher.stop()

    def _call(self, token):
        return self.handler(_make_event("POST", "/auth/refresh", {"refresh_token": token}), None)

    # --- happy path ---

    def test_refresh_returns_200(self):
        token = _make_refresh_token()
        result = self._call(token)
        self.assertEqual(result["statusCode"], 200)

    def test_refresh_returns_new_access_token(self):
        token = _make_refresh_token()
        result = self._call(token)
        body = json.loads(result["body"])
        self.assertIn("access_token", body)
        self.assertEqual(body["token_type"], "Bearer")

    def test_refresh_new_access_token_is_valid_jwt(self):
        token = _make_refresh_token(user_id="uid-1", email="user@example.com")
        result = self._call(token)
        new_token = json.loads(result["body"])["access_token"]
        payload = jwt.decode(new_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertEqual(payload["type"], "access")
        self.assertEqual(payload["email"], "user@example.com")

    def test_refresh_does_not_return_refresh_token(self):
        """Refresh endpoint only issues a new access token, not a new refresh token."""
        token = _make_refresh_token()
        result = self._call(token)
        body = json.loads(result["body"])
        self.assertNotIn("refresh_token", body)

    # --- invalid tokens ---

    def test_refresh_missing_token_returns_400(self):
        result = self.handler(_make_event("POST", "/auth/refresh", {}), None)
        self.assertEqual(result["statusCode"], 400)

    def test_refresh_empty_token_returns_400(self):
        result = self._call("")
        self.assertEqual(result["statusCode"], 400)

    def test_refresh_expired_token_returns_401(self):
        token = _make_refresh_token(expired=True)
        result = self._call(token)
        self.assertEqual(result["statusCode"], 401)
        self.assertIn("expired", json.loads(result["body"])["error"].lower())

    def test_refresh_invalid_signature_returns_401(self):
        token = jwt.encode(
            {"sub": "uid", "email": "x@y.com", "type": "refresh",
             "exp": datetime.now(timezone.utc) + timedelta(days=7),
             "iat": datetime.now(timezone.utc)},
            "wrong-secret",
            algorithm=JWT_ALGORITHM,
        )
        result = self._call(token)
        self.assertEqual(result["statusCode"], 401)

    def test_refresh_malformed_token_returns_401(self):
        result = self._call("this.is.notajwt")
        self.assertEqual(result["statusCode"], 401)

    def test_refresh_access_token_as_refresh_returns_401(self):
        """An access token must not be accepted in the refresh endpoint."""
        token = _make_access_token()
        result = self._call(token)
        self.assertEqual(result["statusCode"], 401)
        self.assertIn("type", json.loads(result["body"])["error"].lower())

    def test_refresh_garbage_string_returns_401(self):
        result = self._call("not-a-token-at-all")
        self.assertEqual(result["statusCode"], 401)


# ---------------------------------------------------------------------------
# lambda_handler routing tests
# ---------------------------------------------------------------------------

class TestRouting(unittest.TestCase):
    def setUp(self):
        self._patcher = patch("auth_lambda.dynamodb")
        self.mock_dynamodb = self._patcher.start()
        import auth_lambda
        self.handler = auth_lambda.lambda_handler

    def tearDown(self):
        self._patcher.stop()

    def test_options_returns_200(self):
        result = self.handler(_make_event("OPTIONS", "/auth/login"), None)
        self.assertEqual(result["statusCode"], 200)

    def test_get_method_returns_405(self):
        result = self.handler(_make_event("GET", "/auth/login"), None)
        self.assertEqual(result["statusCode"], 405)

    def test_put_method_returns_405(self):
        result = self.handler(_make_event("PUT", "/auth/login"), None)
        self.assertEqual(result["statusCode"], 405)

    def test_delete_method_returns_405(self):
        result = self.handler(_make_event("DELETE", "/auth/login"), None)
        self.assertEqual(result["statusCode"], 405)

    def test_unknown_path_returns_404(self):
        result = self.handler(_make_event("POST", "/auth/unknown"), None)
        self.assertEqual(result["statusCode"], 404)

    def test_root_path_returns_404(self):
        result = self.handler(_make_event("POST", "/"), None)
        self.assertEqual(result["statusCode"], 404)

    def test_invalid_json_body_returns_400(self):
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/auth/login",
            "body": "{not valid json",
        }
        result = self.handler(event, None)
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("Invalid JSON", json.loads(result["body"])["error"])

    def test_null_body_treated_as_empty(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/auth/login",
            "body": None,
        }
        result = self.handler(event, None)
        # Should fail validation (missing fields) not crash
        self.assertEqual(result["statusCode"], 400)

    def test_signup_route_dispatches_correctly(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/signup", {"email": "a@b.com", "password": "Password1"}),
            None,
        )
        self.assertIn(result["statusCode"], (201, 400, 409))

    def test_login_route_dispatches_correctly(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/login", {"email": "a@b.com", "password": "Password1"}),
            None,
        )
        self.assertIn(result["statusCode"], (200, 400, 401))


# ---------------------------------------------------------------------------
# Response format / CORS tests
# ---------------------------------------------------------------------------

class TestResponseFormat(unittest.TestCase):
    def setUp(self):
        self._patcher = patch("auth_lambda.dynamodb")
        self.mock_dynamodb = self._patcher.start()
        import auth_lambda
        self.handler = auth_lambda.lambda_handler

    def tearDown(self):
        self._patcher.stop()

    def _signup(self, body=None):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        body = body or {"email": "new@example.com", "password": "Password1"}
        return self.handler(_make_event("POST", "/auth/signup", body), None)

    def test_all_responses_have_content_type_json(self):
        result = self._signup()
        self.assertEqual(result["headers"]["Content-Type"], "application/json")

    def test_all_responses_have_allow_origin_header(self):
        result = self._signup()
        self.assertEqual(result["headers"]["Access-Control-Allow-Origin"], "*")

    def test_all_responses_have_allow_headers(self):
        result = self._signup()
        self.assertIn("Authorization", result["headers"]["Access-Control-Allow-Headers"])

    def test_body_is_valid_json(self):
        result = self._signup()
        parsed = json.loads(result["body"])
        self.assertIsInstance(parsed, dict)

    def test_error_body_has_error_key(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(_make_event("POST", "/auth/signup", {}), None)
        body = json.loads(result["body"])
        self.assertIn("error", body)

    def test_success_body_has_message_key(self):
        result = self._signup()
        body = json.loads(result["body"])
        self.assertIn("message", body)


# ---------------------------------------------------------------------------
# Token expiry / timing tests
# ---------------------------------------------------------------------------

class TestTokenExpiry(unittest.TestCase):
    def setUp(self):
        self._patcher = patch("auth_lambda.dynamodb")
        self.mock_dynamodb = self._patcher.start()
        import auth_lambda
        self.handler = auth_lambda.lambda_handler

    def tearDown(self):
        self._patcher.stop()

    def test_access_token_exp_is_in_future(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/signup", {"email": "new@example.com", "password": "Password1"}),
            None,
        )
        token = json.loads(result["body"])["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertGreater(payload["exp"], time.time())

    def test_refresh_token_exp_is_further_than_access_token(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/signup", {"email": "new@example.com", "password": "Password1"}),
            None,
        )
        body = json.loads(result["body"])
        access_payload = jwt.decode(body["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        refresh_payload = jwt.decode(body["refresh_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertGreater(refresh_payload["exp"], access_payload["exp"])

    def test_token_contains_iat_claim(self):
        table = _mock_table(get_item_return={})
        self.mock_dynamodb.Table.return_value = table
        result = self.handler(
            _make_event("POST", "/auth/signup", {"email": "new@example.com", "password": "Password1"}),
            None,
        )
        token = json.loads(result["body"])["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertIn("iat", payload)


if __name__ == "__main__":
    unittest.main()
