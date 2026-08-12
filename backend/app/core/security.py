import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hmac.new(salt.encode(), password.encode(), hashlib.sha256)
    return f"{salt}:{h.hexdigest()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored = password_hash.split(":", 1)
        h = hmac.new(salt.encode(), password.encode(), hashlib.sha256)
        return hmac.compare_digest(h.hexdigest(), stored)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
