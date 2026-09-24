import os
from dotenv import load_dotenv

load_dotenv()

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is not set")

JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
JWT_ISSUER = f"{SUPABASE_URL}/auth/v1"

jwks_client = PyJWKClient(JWKS_URL)


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

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )