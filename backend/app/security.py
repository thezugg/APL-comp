import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select
from .models import Admin

# Set a persistent random secret via environment, not a default in source control.
JWT_SECRET = os.environ.get("JWT_SECRET", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
FAILED_LOGINS = {}


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, saved: str) -> bool:
    try:
        algorithm, rounds, salt, digest = saved.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(computed, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def issue_token(admin_id: int):
    csrf = secrets.token_urlsafe(24)
    token = jwt.encode({"sub": str(admin_id), "csrf": csrf,
                        "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
                       JWT_SECRET, algorithm="HS256")
    return token, csrf


def current_admin(request: Request, session):
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise HTTPException(503, "Server authentication not configured")
    token = request.cookies.get("pool_session", "")
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        admin = session.get(Admin, int(claims["sub"]))
        if admin is None or not admin.active:
            raise ValueError("User inactive")
        return admin, claims
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Please sign in as a committee administrator")


def require_admin(request: Request, session, write=False):
    admin, claims = current_admin(request, session)
    if write:
        supplied = request.headers.get("X-CSRF-Token", "")
        if not supplied or not hmac.compare_digest(supplied, claims["csrf"]):
            raise HTTPException(403, "Invalid CSRF token")
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.headers.get("host"):
                # For Vite development the browser proxy forwards the original Host.
                raise HTTPException(403, "Invalid request origin")
    return admin


def check_login_attempt(ip: str, ok: bool):
    now = time.monotonic()
    times = [x for x in FAILED_LOGINS.get(ip, []) if now - x < 900]
    if ok:
        FAILED_LOGINS.pop(ip, None)
        return
    if len(times) >= 7:
        raise HTTPException(429, "Too many login attempts. Try again later")
    times.append(now)
    FAILED_LOGINS[ip] = times
