import json
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

import re

import boto3
import bcrypt
import jwt

logger = logging.getLogger()
logger.setLevel(logging.INFO)

USERS_TABLE = os.environ.get("USERS_TABLE", "seng3011-users")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-to-a-strong-secret-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

dynamodb = boto3.resource("dynamodb")


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Content-Type": "application/json",
    }


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(body),
    }


def _create_token(user_id, email, token_type="access"):
    if token_type == "access":
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": user_id,
        "email": email,
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _validate_email(email):
    pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    return bool(re.match(pattern, email))


def _validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number"
    return None


def handle_signup(body):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "").strip()

    if not email or not password:
        return _response(400, {"error": "Email and password are required"})

    if not _validate_email(email):
        return _response(400, {"error": "Invalid email address"})

    password_error = _validate_password(password)
    if password_error:
        return _response(400, {"error": password_error})

    table = dynamodb.Table(USERS_TABLE)

    existing = table.get_item(Key={"email": email})
    if "Item" in existing:
        return _response(409, {"error": "Email already registered"})

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    table.put_item(Item={
        "email": email,
        "user_id": user_id,
        "name": name,
        "password_hash": password_hash,
        "created_at": now,
        "updated_at": now,
    })

    logger.info("New user registered: %s", email)

    access_token = _create_token(user_id, email, "access")
    refresh_token = _create_token(user_id, email, "refresh")

    return _response(201, {
        "message": "Account created successfully",
        "user": {"id": user_id, "email": email, "name": name},
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    })


def handle_login(body):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        return _response(400, {"error": "Email and password are required"})

    table = dynamodb.Table(USERS_TABLE)
    result = table.get_item(Key={"email": email})

    if "Item" not in result:
        # Constant-time response to prevent user enumeration
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        return _response(401, {"error": "Invalid email or password"})

    user = result["Item"]

    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return _response(401, {"error": "Invalid email or password"})

    logger.info("User logged in: %s", email)

    access_token = _create_token(user["user_id"], email, "access")
    refresh_token = _create_token(user["user_id"], email, "refresh")

    return _response(200, {
        "message": "Login successful",
        "user": {"id": user["user_id"], "email": email, "name": user.get("name", "")},
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    })


def handle_refresh(body):
    token = body.get("refresh_token", "")

    if not token:
        return _response(400, {"error": "Refresh token required"})

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return _response(401, {"error": "Refresh token expired, please log in again"})
    except jwt.InvalidTokenError:
        return _response(401, {"error": "Invalid refresh token"})

    if payload.get("type") != "refresh":
        return _response(401, {"error": "Invalid token type"})

    access_token = _create_token(payload["sub"], payload["email"], "access")

    return _response(200, {
        "access_token": access_token,
        "token_type": "Bearer",
    })


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return _response(200, {})

    if method != "POST":
        return _response(405, {"error": "Method not allowed"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    if path == "/auth/signup":
        return handle_signup(body)
    elif path == "/auth/login":
        return handle_login(body)
    elif path == "/auth/refresh":
        return handle_refresh(body)
    else:
        return _response(404, {"error": "Not found"})
