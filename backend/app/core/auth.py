from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
        return None
    # PostgreSQL user IDs are signed 32-bit integers.
    if len(subject) > 10 or not 0 < int(subject) <= 2147483647:
        return None
    result = await db.execute(select(User).where(User.id == int(subject)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    # Reject tokens issued before a password reset (auth_version bump).
    if payload.get("ver", 0) != (user.auth_version or 0):
        return None
    return user


def require_auth(user: User | None = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_seller(user: User = Depends(require_auth)):
    if getattr(user, "restricted_port", None) not in (None, "seller"):
        raise HTTPException(status_code=403, detail="Account is restricted to another portal")
    if user.role not in ("seller", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
    return user


def require_buyer(user: User = Depends(require_auth)):
    if getattr(user, "restricted_port", None) not in (None, "buyer"):
        raise HTTPException(status_code=403, detail="Account is restricted to another portal")
    if user.role not in ("buyer", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buyer access required")
    return user


def require_admin(user: User = Depends(require_auth)):
    if getattr(user, "restricted_port", None) not in (None, "admin"):
        raise HTTPException(status_code=403, detail="Account is restricted to another portal")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
