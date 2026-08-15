from datetime import datetime, timedelta, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update, func
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_uid,
    generate_token,
    hash_token,
)
from app.core.auth import require_auth
from app.models.user import User
from app.models.auth_token import AuthToken
from app.services.email import send_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

VERIFICATION_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(minutes=30)
RESEND_COOLDOWN = timedelta(seconds=60)


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    store_name: str | None = None
    country: str
    phone: str
    role: str = "buyer"


class LoginRequest(BaseModel):
    identifier: str
    password: str
    role: str | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    store_name: str | None = None
    avatar_url: str | None = None
    business_license_url: str | None = None
    phone: str | None = None
    country: str | None = None


class ResendVerificationRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: str
    role: str
    name: str | None = None
    store_name: str | None = None
    avatar_url: str | None = None
    business_license_url: str | None = None
    country: str | None = None
    phone: str | None = None
    uid: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _invalidate_tokens(db: AsyncSession, user_id: int, token_type: str) -> None:
    """Mark all unused tokens of a given type for a user as used."""
    await db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.token_type == token_type,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=_now())
    )


async def _create_token(db: AsyncSession, user_id: int, token_type: str) -> str:
    """Create a one-time token and return the raw value (only its hash is stored)."""
    raw = generate_token()
    ttl = VERIFICATION_TOKEN_TTL if token_type == "email_verification" else RESET_TOKEN_TTL
    db.add(AuthToken(
        user_id=user_id,
        token_hash=hash_token(raw),
        token_type=token_type,
        expires_at=_now() + ttl,
    ))
    await db.flush()
    return raw


async def _find_token(db: AsyncSession, raw: str, token_type: str) -> AuthToken | None:
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == hash_token(raw),
            AuthToken.token_type == token_type,
        )
    )
    return result.scalar_one_or_none()


async def _recently_requested(db: AsyncSession, user_ids: list[int], token_type: str) -> bool:
    """Return True if any of the given users requested this token type within the cooldown."""
    if not user_ids:
        return False
    result = await db.execute(
        select(func.max(AuthToken.created_at)).where(
            AuthToken.user_id.in_(user_ids),
            AuthToken.token_type == token_type,
        )
    )
    latest = result.scalar()
    if latest is None:
        return False
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    return (_now() - latest) < RESEND_COOLDOWN


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if data.role not in ("buyer", "seller"):
        raise HTTPException(status_code=400, detail="Invalid role")

    if not data.phone or not data.phone.strip():
        raise HTTPException(status_code=400, detail="Phone number is required")

    if data.role == "seller" and (not data.name or not data.name.strip()):
        raise HTTPException(status_code=400, detail="Company name is required for sellers")

    existing = await db.execute(
        select(User).where(User.email == data.email, User.role == data.role)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this role already exists for this email")

    user = User(
        email=data.email.strip(),
        password_hash=hash_password(data.password),
        role=data.role,
        name=data.name.strip() if data.name else None,
        store_name=data.store_name.strip() if data.store_name else None,
        country=data.country,
        phone=data.phone.strip(),
        uid=generate_uid(),
        email_verified_at=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create verification token and send the email. On failure, keep the account
    # (so the user can resend) but return a clear error.
    token = await _create_token(db, user.id, "email_verification")
    await db.commit()

    sent = await send_verification_email(user.email, token)
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Account created, but we could not send the verification email. "
                   "Please use 'Resend verification email' to try again.",
        )

    return {
        "success": True,
        "message": "Registration successful. Please check your email to verify your account.",
    }


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(
            User.is_active == True,
            or_(
                User.email == data.identifier,
                User.phone == data.identifier,
                User.uid == data.identifier,
            ),
        )
    )
    candidates = result.scalars().all()
    matched = [u for u in candidates if verify_password(data.password, u.password_hash)]

    if not matched:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = None
    if data.role:
        user = next((u for u in matched if u.role == data.role), None)
        if user is None:
            user = next((u for u in matched if u.role == "admin"), None)

    if user is None:
        if len(matched) == 1:
            user = matched[0]
        else:
            raise HTTPException(status_code=401, detail="Multiple accounts found; please sign in with your unique ID")

    # Admins are system-seeded and skip email verification; everyone else must verify.
    if user.role != "admin" and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Please verify your email before signing in.")

    token = create_access_token(user.id, user.role, user.auth_version or 0)
    return AuthResponse(
        token=token, user_id=user.id, email=user.email, role=user.role,
        name=user.name, store_name=user.store_name,
        avatar_url=user.avatar_url, business_license_url=user.business_license_url,
        country=user.country, phone=user.phone, uid=user.uid,
    )


@router.post("/verify-email")
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    token = await _find_token(db, data.token, "email_verification")
    if not token:
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired.")

    user = await db.get(User, token.user_id)

    if token.used_at is not None:
        if user and user.email_verified_at is not None:
            return {"success": True, "message": "Email already verified."}
        raise HTTPException(status_code=400, detail="Verification link has already been used.")

    if token.expires_at < _now():
        raise HTTPException(status_code=400, detail="Verification link has expired.")

    if not user:
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired.")

    user.email_verified_at = _now()
    token.used_at = _now()
    await db.commit()
    return {"success": True, "message": "Email verified successfully."}


@router.post("/resend-verification")
async def resend_verification(data: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    # Single, identical response for every outcome to prevent email enumeration.
    message = "If the account exists and is not verified, a verification email has been sent."

    email = data.email.strip()
    users = (await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )).scalars().all()

    unverified = [u for u in users if u.email_verified_at is None]
    if not unverified:
        # No account, or the account is already verified: do nothing.
        return {"success": True, "message": message}

    user_ids = [u.id for u in unverified]
    if await _recently_requested(db, user_ids, "email_verification"):
        # Rate limited: do not send, but respond identically.
        return {"success": True, "message": message}

    for u in unverified:
        await _invalidate_tokens(db, u.id, "email_verification")

    target = unverified[0]
    token = await _create_token(db, target.id, "email_verification")
    await db.commit()

    sent = await send_verification_email(target.email, token)
    if not sent:
        # Log a safe summary without leaking whether the account exists.
        logger.warning("Verification email could not be sent (send failure)")
        return {"success": True, "message": message}

    return {"success": True, "message": message}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    email = data.email.strip()
    users = (await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )).scalars().all()

    if not users:
        return {"success": True, "message": "If the account exists, a password reset email has been sent."}

    user_ids = [u.id for u in users]
    if await _recently_requested(db, user_ids, "password_reset"):
        # Rate limited but do not reveal that the account exists.
        return {"success": True, "message": "If the account exists, a password reset email has been sent."}

    for u in users:
        await _invalidate_tokens(db, u.id, "password_reset")

    target = users[0]
    token = await _create_token(db, target.id, "password_reset")
    await db.commit()

    sent = await send_password_reset_email(target.email, token)
    if not sent:
        raise HTTPException(status_code=500, detail="Could not send the password reset email. Please try again.")

    return {"success": True, "message": "If the account exists, a password reset email has been sent."}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    token = await _find_token(db, data.token, "password_reset")
    if not token:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
    if token.used_at is not None:
        raise HTTPException(status_code=400, detail="Reset link has already been used.")
    if token.expires_at < _now():
        raise HTTPException(status_code=400, detail="Reset link has expired.")

    user = await db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")

    user.password_hash = hash_password(data.new_password)
    user.auth_version = (user.auth_version or 0) + 1
    await _invalidate_tokens(db, user.id, "password_reset")
    token.used_at = _now()
    await db.commit()

    return {"success": True, "message": "Password has been reset. You can now sign in."}


@router.post("/change-password", response_model=AuthResponse)
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password")

    user.password_hash = hash_password(data.new_password)
    user.auth_version = (user.auth_version or 0) + 1
    await db.commit()

    # Issue a fresh token so the current device stays logged in while all
    # previously issued tokens become invalid.
    token = create_access_token(user.id, user.role, user.auth_version or 0)
    return AuthResponse(
        token=token, user_id=user.id, email=user.email, role=user.role,
        name=user.name, store_name=user.store_name,
        avatar_url=user.avatar_url, business_license_url=user.business_license_url,
        country=user.country, phone=user.phone, uid=user.uid,
    )


@router.get("/me", response_model=AuthResponse)
async def me(user: User = Depends(require_auth)):
    return AuthResponse(
        token="", user_id=user.id, email=user.email, role=user.role,
        name=user.name, store_name=user.store_name,
        avatar_url=user.avatar_url, business_license_url=user.business_license_url,
        country=user.country, phone=user.phone, uid=user.uid,
    )


@router.put("/me", response_model=AuthResponse)
async def update_me(
    data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    if data.name is not None:
        user.name = data.name.strip() or None
    if data.store_name is not None:
        user.store_name = data.store_name.strip() or None
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url.strip() or None
    if data.business_license_url is not None:
        user.business_license_url = data.business_license_url.strip() or None
    # Phone numbers are managed via /api/auth/phones. `users.phone` is kept as a
    # legacy primary mirror and must not be overwritten through this endpoint.
    # The `phone` field remains in the request schema for backward compatibility
    # but is intentionally ignored here.
    if data.country is not None:
        user.country = data.country
    await db.commit()
    await db.refresh(user)
    return AuthResponse(
        token="", user_id=user.id, email=user.email, role=user.role,
        name=user.name, store_name=user.store_name,
        avatar_url=user.avatar_url, business_license_url=user.business_license_url,
        country=user.country, phone=user.phone, uid=user.uid,
    )
