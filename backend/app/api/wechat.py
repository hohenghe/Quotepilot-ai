from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
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
from app.services.wechat import code_to_session, WechatLoginError
from app.services.email import send_verification_email

router = APIRouter(prefix="/api/auth", tags=["wechat-auth"])


class WechatLoginRequest(BaseModel):
    code: str


class WechatBindRequest(BaseModel):
    code: str
    identifier: str
    password: str


class WechatRegisterRequest(BaseModel):
    code: str
    email: str
    password: str
    name: str | None = None
    country: str
    phone: str


class WechatAuthResponse(BaseModel):
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


@router.post("/wechat-login", response_model=WechatAuthResponse)
async def wechat_login(data: WechatLoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        session = await code_to_session(data.code)
    except WechatLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="WeChat login failed")

    openid = session["openid"]

    result = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.openid == openid)
    )
    account = result.scalar_one_or_none()
    if not account:
        return WechatAuthResponse(bound=False)

    user = await db.get(User, account.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    if user.role != "admin" and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Please verify your email before signing in.")

    return WechatAuthResponse(**_auth_payload(user))


@router.post("/wechat-register")
async def wechat_register(data: WechatRegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        session = await code_to_session(data.code)
    except WechatLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="WeChat login failed")

    openid = session["openid"]
    unionid = session.get("unionid")

    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not data.phone or not data.phone.strip():
        raise HTTPException(status_code=400, detail="Phone number is required")
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Company name is required for sellers")

    existing_bind = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.openid == openid)
    )
    if existing_bind.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This WeChat account is already bound to a seller")

    existing_user = await db.execute(
        select(User).where(User.email == data.email.strip(), User.role == "seller")
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this role already exists for this email")

    user = User(
        email=data.email.strip(),
        password_hash=hash_password(data.password),
        role="seller",
        name=data.name.strip(),
        store_name=None,
        country=data.country,
        phone=data.phone.strip(),
        uid=generate_uid(),
        email_verified_at=None,
    )
    db.add(user)
    await db.flush()
    db.add(SellerWechatAccount(user_id=user.id, openid=openid, unionid=unionid))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This WeChat account is already bound to a seller")

    await db.refresh(user)

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
        session = await code_to_session(data.code)
    except WechatLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))
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
            return WechatAuthResponse(**_auth_payload(user))
        raise HTTPException(status_code=409, detail="This WeChat account is already bound to another seller")

    bound_user = await db.execute(
        select(SellerWechatAccount).where(SellerWechatAccount.user_id == user.id)
    )
    if bound_user.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This seller account is already bound to a WeChat account")

    db.add(SellerWechatAccount(user_id=user.id, openid=openid, unionid=unionid))
    await db.commit()

    return WechatAuthResponse(**_auth_payload(user))
