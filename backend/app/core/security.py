import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from app.core.config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
_password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)


def generate_uid() -> str:
    return uuid.uuid4().hex[:12].upper()


def generate_token() -> str:
    """Generate a cryptographically secure one-time token (URL-safe)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for storage. Only the hash is persisted, never the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_email_code() -> str:
    """Six decimal digits, including leading zeroes, from the system CSPRNG."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_code(user_id: int, code: str) -> str:
    """A keyed digest prevents offline guessing if only the database leaks."""
    message = f"email-verification:{user_id}:{code}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def hash_admin_email_test_code(admin_id: int, email: str, code: str) -> str:
    """Bind a delivery-test code to its admin and recipient, separate from signup."""
    message = f"admin-email-test:{admin_id}:{email.strip().lower()}:{code}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    """Argon2id encodes a fresh random salt and its cost parameters in the hash."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith("$argon2id$"):
        try:
            return _password_hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError, ValueError):
            return False
    # Legacy salted HMAC-SHA256. Upgrade only after a successful login.
    try:
        salt, stored = password_hash.split(":", 1)
        if len(salt) != 32 or len(stored) != 64:
            return False
        bytes.fromhex(salt)
        bytes.fromhex(stored)
        h = hmac.new(salt.encode(), password.encode(), hashlib.sha256)
        return hmac.compare_digest(h.hexdigest(), stored)
    except (ValueError, AttributeError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith("$argon2id$"):
        return _password_hasher.check_needs_rehash(password_hash)
    return len(password_hash.split(":", 1)) == 2


def create_access_token(user_id: int, role: str, auth_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "ver": auth_version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
