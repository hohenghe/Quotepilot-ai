from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import require_seller
from app.models.user import User
from app.services.rating import compute_seller_score

router = APIRouter(prefix="/api/sellers", tags=["sellers"])


@router.get("/score")
async def seller_score(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    score = await compute_seller_score(db, user.id)
    return {"score": score}
