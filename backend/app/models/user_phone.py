from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class UserPhone(Base):
    """Phone numbers associated with a user.

    `is_primary` marks the single primary phone (mirrored into users.phone for
    legacy compatibility). Additional phones can be bound/unbound; primary
    phones cannot be removed. `verified` reflects SMS OTP verification (not yet
    implemented — see app/services for the future OTP step).
    """

    __tablename__ = "user_phones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    phone = Column(String(50), nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
