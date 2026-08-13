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
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    return result.scalar_one_or_none()


def require_auth(user: User | None = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_seller(user: User = Depends(require_auth)):
    if user.role != "seller":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
    return user


def require_buyer(user: User = Depends(require_auth)):
    if user.role != "buyer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buyer access required")
    return user


def require_admin(user: User = Depends(require_auth)):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
