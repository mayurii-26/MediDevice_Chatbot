"""
admin/auth.py
─────────────────────────────────────────────────────────────────────────────
Completely independent admin authentication.

Design
------
- Credentials are stored ONLY in environment variables:
      ADMIN_USERNAME   — plain text username
      ADMIN_PASSWORD   — plain text password  (use a strong value in production)
      ADMIN_JWT_SECRET — secret used to sign admin JWTs
- Uses python-jose for JWT signing/verification.
- Has NO dependency on Supabase, the user auth flow, or any user table.
- The admin JWT is stored in localStorage on the frontend under the key
  "admin_token" and is validated on every protected admin API call via the
  `require_admin` dependency.

Token payload
─────────────
{
    "sub":  "admin",
    "role": "admin",
    "iat":  <unix timestamp>,
    "exp":  <unix timestamp + ADMIN_TOKEN_EXPIRE_HOURS * 3600>
}
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

# ── Load .env from project root (two levels up from this file) ─────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_HERE)
_ROOT_DIR    = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_ROOT_DIR, ".env"))

# ── Config ─────────────────────────────────────────────────────────────────
ADMIN_USERNAME:  str = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD:  str = os.getenv("ADMIN_PASSWORD", "changeme_in_production")
ADMIN_JWT_SECRET: str = os.getenv(
    "ADMIN_JWT_SECRET",
    "INSECURE_FALLBACK_SECRET_CHANGE_THIS",
)
ADMIN_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ADMIN_TOKEN_EXPIRE_HOURS", "8"))
ALGORITHM = "HS256"

# ── Bearer extractor ───────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


# ── Token helpers ──────────────────────────────────────────────────────────

def create_admin_token() -> str:
    """
    Create a signed JWT for an authenticated admin session.
    Returns the token string.
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub":  "admin",
        "role": "admin",
        "iat":  int(now.timestamp()),
        "exp":  int((now + timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, ADMIN_JWT_SECRET, algorithm=ALGORITHM)


def decode_admin_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT.
    Returns the payload dict if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            return None
        return payload
    except JWTError:
        return None


# ── FastAPI dependency ─────────────────────────────────────────────────────

def require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """
    FastAPI dependency — injects the admin token payload if the request
    carries a valid admin JWT in the Authorization header.

    Usage in a route:
        @router.get("/admin/something")
        def something(_admin=Depends(require_admin)):
            ...

    Raises HTTP 401 if the token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_admin_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ── Credential validator ───────────────────────────────────────────────────

def validate_admin_credentials(username: str, password: str) -> bool:
    """
    Returns True only when both username and password match the env-configured
    admin credentials.  No database lookup is performed.
    """
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
