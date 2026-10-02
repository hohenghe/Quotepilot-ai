import asyncio
from datetime import datetime, timedelta, timezone
import logging
import time

import jwt

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, StrictBool

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_password,
    generate_uid,
    hash_password,
    generate_token,
    hash_token,
)
from app.models.user import User
from app.models.auth_token import AuthToken
from app.models.seller_wechat_account import SellerWechatAccount
from app.models.user_phone import UserPhone
from app.services.wechat import code_to_session, get_phone_number, warm_phone_access_token, WechatLoginError
from app.services.email import send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["wechat-auth"])


class WechatLoginRequest(BaseModel):
    code: str | None = None
    session_token: str | None = None
    phone_code: str


class WechatSessionRequest(BaseModel):
    code: str


_WECHAT_SESSION_LIFETIME_SECONDS = 120


def _create_wechat_session_token(session: dict) -> str:
    return jwt.encode(
        {
            "purpose": "wechat_phone_login",
            "openid": session["openid"],
            "unionid": session.get("unionid"),
            "exp": datetime.now(timezone.utc) + timedelta(seconds=_WECHAT_SESSION_LIFETIME_SECONDS),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )


def _decode_wechat_session_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="WeChat session expired") from exc
    if payload.get("purpose") != "wechat_phone_login" or not isinstance(payload.get("openid"), str) or not payload["openid"]:
        raise HTTPException(status_code=400, detail="WeChat session expired")
    return {"openid": payload["openid"], "unionid": payload.get("unionid")}


class WechatBindRequest(BaseModel):
    code: str
    phone_code: str
    identifier: str
    password: str


class WechatRegisterRequest(BaseModel):
    supports_distribution: StrictBool
    code: str
    phone_code: str
    email: str | None = None
    password: str
    name: str | None = None
    country: str
    # Kept only for compatibility with old clients. For WeChat registration,
    # the number stored below always comes from the official authorization API.
    phone: str | None = None


class WechatAuthResponse(BaseModel):
    supports_distribution: bool | None = None
    bound: bool
    token: str | None = None
    user_id: int | None = None
    email: str | None = None
    role: str | None = None
    name: str | None = None
    store_name: str | None = None
    avatar_url: str | None = None
    business_license_url: str | None = None
    country: str | None = None
    phone: str | None = None
    uid: str | None = None


def _auth_payload(user: User) -> dict:
    return {
        "bound": True,
        "supports_distribution": user.supports_distribution,
        "token": create_access_token(user.id, user.role, user.auth_version or 0),
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "store_name": user.store_name,
        "avatar_url": user.avatar_url,
        "business_license_url": user.business_license_url,
        "country": user.country,
        "phone": user.phone,
        "uid": user.uid,
    }


async def _resolve_wechat_credentials(code: str, phone_code: str) -> tuple[dict, str]:
    """Fetch independent WeChat credentials concurrently to reduce login TTFB."""
    session, phone = await asyncio.gather(
        code_to_session(code),
        get_phone_number(phone_code),
    )
    return session, phone


async def _set_wechat_primary_phone(db: AsyncSession, user: User, phone: str) -> None:
    """Promote the officially authorized number; retain the old primary as additional."""
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    conflict = await db.execute(select(User.id).where(User.phone == phone, User.id != user.id).limit(1))
    if conflict.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="This phone number is already in use")
    result = await db.execute(select(UserPhone).where(UserPhone.phone == phone, UserPhone.deleted_at.is_(None)))
    target = result.scalar_one_or_none()
    if target and target.user_id != user.id:
        raise HTTPException(status_code=409, detail="This phone number is already in use")
    records = (await db.execute(select(UserPhone).where(
        UserPhone.user_id == user.id, UserPhone.deleted_at.is_(None)
    ))).scalars().all()
    for record in records:
        record.is_primary = False
    # Flush demotions first to respect the partial unique primary-phone index.
    await db.flush()
    if user.phone and user.phone != phone and not any(r.phone == user.phone for r in records):
        db.add(UserPhone(user_id=user.id, phone=user.phone, is_primary=False, verified=False))
    if target is None:
        target = UserPhone(user_id=user.id, phone=phone)
        db.add(target)
    target.is_primary = True
    target.verified = True
    target.verified_at = datetime.now(timezone.utc)
    user.phone = phone


@router.post("/wechat-session")
async def prepare_wechat_session(data: WechatSessionRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Prepare WeChat identity and any existing seller login before a tap."""
    try:
        session = await code_to_session(data.code)
    except Exception:
        logger.warning("WeChat session preparation failed")
        raise HTTPException(status_code=502, detail="WeChat login service is temporarily unavailable")
    result = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.openid == session["openid"])
    )
    account = result.scalar_one_or_none()
    auth_result = None
    if account:
        user = await db.get(User, account.user_id)
        if user and user.is_active and getattr(user, "restricted_port", None) in (None, "seller"):
            if user.role == "admin" or not user.email or user.email_verified_at is not None:
                auth_result = _auth_payload(user)
    else:
        background_tasks.add_task(_warm_phone_token_safely)
    return {
        "session_token": _create_wechat_session_token(session),
        "expires_in": _WECHAT_SESSION_LIFETIME_SECONDS,
        "auth_result": auth_result,
    }


async def _warm_phone_token_safely() -> None:
    try:
        await warm_phone_access_token()
    except Exception:
        logger.warning("WeChat phone access token prefetch failed")


@router.post("/wechat-login", response_model=WechatAuthResponse)
async def wechat_login(data: WechatLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    started = time.perf_counter()
    if bool(data.code) == bool(data.session_token):
        raise HTTPException(status_code=400, detail="Provide either code or session_token")
    try:
        if data.session_token:
            session = _decode_wechat_session_token(data.session_token)
        else:
            session = await code_to_session(data.code)
    except WechatLoginError as e:
        logger.warning("WeChat credential exchange failed: %s", e)
        raise HTTPException(status_code=502, detail="WeChat login service is temporarily unavailable")
    except HTTPException:
        raise
    except Exception:
        logger.warning("WeChat credential exchange failed")
        raise HTTPException(status_code=502, detail="WeChat login failed")

    session_ms = (time.perf_counter() - started) * 1000
    openid = session["openid"]

    result = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.openid == openid)
    )
    account = result.scalar_one_or_none()
    lookup_ms = (time.perf_counter() - started) * 1000 - session_ms
    if not account:
        try:
            phone = await get_phone_number(data.phone_code)
        except WechatLoginError as e:
            logger.warning("WeChat phone exchange failed: %s", e)
            raise HTTPException(status_code=502, detail="WeChat login service is temporarily unavailable")
        except Exception:
            logger.warning("WeChat phone exchange failed")
            raise HTTPException(status_code=502, detail="WeChat login failed")
        phone_ms = (time.perf_counter() - started) * 1000 - session_ms - lookup_ms
        # A WeChat-authorized phone is the seller's verified primary identifier.
        # Create its seller account in one transaction so the first quick login
        # reaches the dashboard without an email-registration detour.
        user = User(
            email=None,
            password_hash=None,
            role="seller",
            supports_distribution=None,
            name=f"商家 {phone[-4:]}" if len(phone) >= 4 else "商家",
            store_name=None,
            country="CN",
            phone=phone,
            uid=generate_uid(),
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        try:
            await db.flush()
            await _set_wechat_primary_phone(db, user, phone)
            db.add(SellerWechatAccount(user_id=user.id, openid=openid, unionid=session.get("unionid")))
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="This phone number or WeChat account is already in use")
        await db.refresh(user)
        response.headers["Server-Timing"] = (
            f"wechat_session;dur={session_ms:.1f}, db;dur={(time.perf_counter() - started) * 1000 - session_ms - phone_ms:.1f}, "
            f"wechat_phone;dur={phone_ms:.1f}"
        )
        return WechatAuthResponse(**_auth_payload(user))

    user = await db.get(User, account.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    if getattr(user, "restricted_port", None) not in (None, "seller"):
        raise HTTPException(status_code=403, detail="Account cannot sign in to the seller portal")

    if user.role != "admin" and user.email and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Please verify your email before signing in.")

    try:
        phone = await get_phone_number(data.phone_code)
    except Exception:
        logger.warning("WeChat phone exchange failed")
        raise HTTPException(status_code=502, detail="WeChat login service is temporarily unavailable")
    try:
        await _set_wechat_primary_phone(db, user, phone)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This phone number is already in use")
    await db.refresh(user)

    response.headers["Server-Timing"] = (
        f"wechat_session;dur={session_ms:.1f}, db;dur={(time.perf_counter() - started) * 1000 - session_ms:.1f}"
    )
    return WechatAuthResponse(**_auth_payload(user))


@router.post("/wechat-register")
async def wechat_register(data: WechatRegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        session, phone = await _resolve_wechat_credentials(data.code, data.phone_code)
    except WechatLoginError as e:
        logger.warning("WeChat code_to_session failed: %s", e)
        raise HTTPException(status_code=502, detail="WeChat login service is temporarily unavailable")
    except Exception:
        raise HTTPException(status_code=502, detail="WeChat login failed")

    openid = session["openid"]
    unionid = session.get("unionid")

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Company name is required for sellers")

    existing_bind = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.openid == openid)
    )
    if existing_bind.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This WeChat account is already bound to a seller")

    email = data.email.strip() if data.email else None
    if email:
        existing_user = await db.execute(
            select(User).where(User.email == email, User.role == "seller")
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="An account with this role already exists for this email")

    user = User(
        email=email,
        password_hash=hash_password(data.password),
        role="seller",
        supports_distribution=data.supports_distribution,
        name=data.name.strip(),
        store_name=None,
        country=data.country,
        phone=phone,
        uid=generate_uid(),
        email_verified_at=None if email else datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    db.add(UserPhone(user_id=user.id, phone=phone, is_primary=True, verified=True))
    db.add(SellerWechatAccount(user_id=user.id, openid=openid, unionid=unionid))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This WeChat account is already bound to a seller")

    await db.refresh(user)

    if not user.email:
        return {"success": True, "message": "Registration successful. You can now sign in with WeChat."}

    raw = generate_token()
    db.add(AuthToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        token_type="email_verification",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    await db.commit()

    sent = await send_verification_email(user.email, raw)
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


@router.post("/wechat-bind", response_model=WechatAuthResponse)
async def wechat_bind(data: WechatBindRequest, db: AsyncSession = Depends(get_db)):
    try:
        session, phone = await _resolve_wechat_credentials(data.code, data.phone_code)
    except WechatLoginError as e:
        logger.warning("WeChat code_to_session failed: %s", e)
        raise HTTPException(status_code=502, detail="WeChat login service is temporarily unavailable")
    except Exception:
        raise HTTPException(status_code=502, detail="WeChat login failed")

    openid = session["openid"]
    unionid = session.get("unionid")

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
    user = next((u for u in matched if u.role == "seller"), None)

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Please verify your email before binding.")

    existing = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.openid == openid)
    )
    account = existing.scalar_one_or_none()
    if account:
        if account.user_id == user.id:
            try:
                await _set_wechat_primary_phone(db, user, phone)
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail="This phone number is already in use")
            return WechatAuthResponse(**_auth_payload(user))
        raise HTTPException(status_code=409, detail="This WeChat account is already bound to another seller")

    bound_user = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.user_id == user.id)
    )
    if bound_user.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This seller account is already bound to a WeChat account")

    db.add(SellerWechatAccount(user_id=user.id, openid=openid, unionid=unionid))
    try:
        await _set_wechat_primary_phone(db, user, phone)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This phone number or WeChat account is already in use")

    return WechatAuthResponse(**_auth_payload(user))
