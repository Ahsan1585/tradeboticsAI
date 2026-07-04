"""Supabase JWT verification for FastAPI.

Every protected endpoint uses `user_id: str = Depends(get_current_user)`.
The user id comes from the VERIFIED token's `sub` claim — never from a
client-supplied query param or body field.

Supports both Supabase auth configurations:
- Legacy projects: HS256 shared secret -> set SUPABASE_JWT_SECRET
  (Supabase dashboard -> Project Settings -> API -> JWT Secret).
- New projects with asymmetric signing keys: leave SUPABASE_JWT_SECRET
  unset; tokens are verified against the project's JWKS endpoint.
"""
import os
import sys

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Request

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not SUPABASE_URL:
            raise HTTPException(status_code=500, detail="Auth misconfigured: SUPABASE_URL missing.")
        _jwks_client = PyJWKClient(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
        )
    return _jwks_client


def _decode(token: str) -> dict:
    if SUPABASE_JWT_SECRET:
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256"],
        audience="authenticated",
    )


async def get_current_user(request: Request) -> str:
    """Returns the authenticated user's UUID or raises 401."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = auth_header[len("Bearer "):].strip()
    try:
        claims = _decode(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
    except Exception as e:
        print(f"[AUTH] token rejected: {type(e).__name__}: {e}", file=sys.stderr)
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")
    return user_id
