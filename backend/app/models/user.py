from sqlalchemy import Column, Integer, String, DateTime, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", "role", name="uq_users_email_role"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(300), nullable=False, index=True)
    password_hash = Column(String(300), nullable=False)
    role = Column(String(20), nullable=False, default="seller")
    name = Column(String(200), nullable=True)
    store_name = Column(String(200), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    business_license_url = Column(String(500), nullable=True)
    country = Column(String(100), nullable=False, default="CN")
    phone = Column(String(50), nullable=True)
    uid = Column(String(32), nullable=True, unique=True, index=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    auth_version = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
