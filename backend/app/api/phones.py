from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import require_auth
from app.models.user import User
from app.models.user_phone import UserPhone

router = APIRouter(prefix="/api/auth", tags=["phones"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AddPhoneRequest(BaseModel):
    phone: str


class PhoneResponse(BaseModel):
    id: int
    phone: str
    is_primary: bool
    verified: bool
    verified_at: str | None = None


def _serialize(p: UserPhone) -> dict:
    return {
        "id": p.id,
        "phone": p.phone,
        "is_primary": p.is_primary,
        "verified": p.verified,
        "verified_at": p.verified_at.isoformat() if p.verified_at else None,
    }


@router.get("/phones", response_model=list[PhoneResponse])
async def list_phones(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    result = await db.execute(
        select(UserPhone)
        .where(UserPhone.user_id == user.id, UserPhone.deleted_at.is_(None))
        .order_by(UserPhone.is_primary.desc(), UserPhone.id)
    )
    return [_serialize(p) for p in result.scalars().all()]


@router.post("/phones", response_model=PhoneResponse)
async def add_phone(
    data: AddPhoneRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    phone = data.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    existing = await db.execute(
        select(UserPhone).where(
            UserPhone.phone == phone,
            UserPhone.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This phone number is already in use")

    # No SMS OTP infrastructure yet: new phone numbers are added unverified and
    # can never become primary or affect users.phone (the legacy primary mirror).
    record = UserPhone(user_id=user.id, phone=phone, is_primary=False, verified=False)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _serialize(record)


@router.delete("/phones/{phone_id}")
async def remove_phone(
    phone_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    result = await db.execute(
        select(UserPhone).where(
            UserPhone.id == phone_id,
            UserPhone.user_id == user.id,
            UserPhone.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Phone number not found")

    if record.is_primary:
        raise HTTPException(status_code=400, detail="Primary phone number cannot be removed")

    record.deleted_at = _now()
    await db.commit()
    return {"ok": True, "id": record.id}
