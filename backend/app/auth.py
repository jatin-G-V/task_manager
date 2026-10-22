import os
import logging
from dotenv import load_dotenv

load_dotenv()

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient, PyJWKClientError

from app.db.supabase_client import supabase

SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is not set")

JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
JWT_ISSUER = f"{SUPABASE_URL}/auth/v1"

jwks_client = PyJWKClient(JWKS_URL)
logger = logging.getLogger(__name__)


def _verify_with_supabase(token: str) -> str:
    """Ask Supabase Auth to validate tokens that local JWKS validation cannot."""
    try:
        response = supabase.auth.get_user(token)
        user = getattr(response, "user", None)
        user_id = getattr(user, "id", None)
        if user_id:
            return user_id
    except Exception as exc:
        status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        if status in (401, 403):
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
        logger.warning("Supabase token verification failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Could not verify your session. Please try again.",
        ) from exc

    raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ", 1)[1]

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            issuer=JWT_ISSUER,
            audience="authenticated",
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID missing from token"
            )

        return user_id

    except (jwt.PyJWTError, PyJWKClientError) as exc:
        # Supabase projects can use different JWT signing configurations. The
        # local verifier handles ES256/JWKS quickly; Auth is the source of truth
        # when the token cannot be verified with those keys (for example, a
        # legacy HS256 token).
        logger.info("Local JWT verification failed (%s); checking Supabase Auth", type(exc).__name__)
        return _verify_with_supabase(token)
