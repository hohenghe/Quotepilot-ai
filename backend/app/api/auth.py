from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, generate_uid
from app.core.auth import require_auth
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    country: str
    phone: str
    role: str = "buyer"


class LoginRequest(BaseModel):
    identifier: str
    password: str
    role: str | None = None


class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: str
    role: str
    name: str | None = None
    country: str | None = None
    phone: str | None = None
    uid: str | None = None


@router.post("/register", response_model=AuthResponse)
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
        country=data.country,
        phone=data.phone.strip(),
        uid=generate_uid(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    return AuthResponse(
        token=token, user_id=user.id, email=user.email, role=user.role,
        name=user.name, country=user.country, phone=user.phone, uid=user.uid,
    )


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

    token = create_access_token(user.id, user.role)
    return AuthResponse(
        token=token, user_id=user.id, email=user.email, role=user.role,
        name=user.name, country=user.country, phone=user.phone, uid=user.uid,
    )


@router.get("/me", response_model=AuthResponse)
async def me(user: User = Depends(require_auth)):
    return AuthResponse(
        token="", user_id=user.id, email=user.email, role=user.role,
        name=user.name, country=user.country, phone=user.phone, uid=user.uid,
    )
