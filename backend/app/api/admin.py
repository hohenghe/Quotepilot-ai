from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.product import Product
from app.models.inquiry import Inquiry, InquiryAnalysis
from app.models.quote import Quote
from app.models.seller_inquiry import SellerInquiry

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.delete("/reset")
async def reset_all(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """Admin: delete all inquiries, products, and seller/buyer accounts (in FK-safe order)."""
    await db.execute(delete(SellerInquiry))
    await db.execute(delete(Quote))
    await db.execute(delete(InquiryAnalysis))
    await db.execute(delete(Inquiry))
    await db.execute(delete(Product))
    await db.execute(delete(User).where(User.role.in_(["seller", "buyer"])))
    await db.commit()
    return {"ok": True}
