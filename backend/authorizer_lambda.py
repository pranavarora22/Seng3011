"""
JWT authorizer Lambda for API Gateway HTTP API.
Validates Bearer tokens on protected routes.
"""
import os
import logging

import jwt

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-to-a-strong-secret-in-production")
JWT_ALGORITHM = "HS256"


def lambda_handler(event, context):
    auth_header = (event.get("headers") or {}).get("authorization", "")

    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or malformed Authorization header")
        return {"isAuthorized": False}

    token = auth_header[7:]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return {"isAuthorized": False}
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token: %s", e)
        return {"isAuthorized": False}

    if payload.get("type") != "access":
        logger.warning("Wrong token type: %s", payload.get("type"))
        return {"isAuthorized": False}

    return {
        "isAuthorized": True,
        "context": {
            "user_id": payload["sub"],
            "email": payload["email"],
        },
    }
