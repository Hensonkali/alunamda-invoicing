import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from database import async_session
from models import User
from config import get_settings

settings = get_settings()
COOKIE_NAME = "alunamda_token"
CSRF_TOKEN_NAME = "alunamda_csrf"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 100000)
        return hmac.compare_digest(key, bytes.fromhex(key_hex))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def validate_csrf_token(token: str, stored: str) -> bool:
    if not token or not stored:
        return False
    return hmac.compare_digest(token, stored)


async def get_current_user(request: Request) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = decode_token(token)
    if not user_id:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def require_auth(request: Request) -> User:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


async def require_admin(request: Request) -> User:
    user = await require_auth(request)
    if user.role != "admin":
        raise HTTPException(status_code=403)
    return user


def login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=302)
