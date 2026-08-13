from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.product import Product
from app.models.inquiry import Inquiry, InquiryAnalysis
from app.models.quote import Quote
from app.models.seller_inquiry import SellerInquiry
from app.models.saved_product import SavedProduct
from app.models.review import Review
from app.services.rating import compute_seller_score

router = APIRouter(prefix="/api/admin", tags=["admin"])


class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.delete("/reset")
async def reset_all(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """Admin: delete all inquiries, products, and seller/buyer accounts (in FK-safe order)."""
    await db.execute(delete(SellerInquiry))
    await db.execute(delete(Quote))
    await db.execute(delete(InquiryAnalysis))
    await db.execute(delete(Inquiry))
    await db.execute(delete(Review))
    await db.execute(delete(SavedProduct))
    await db.execute(delete(Product))
    await db.execute(delete(User).where(User.role.in_(["seller", "buyer"])))
    await db.commit()
    return {"ok": True}


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(User).where(User.role.in_(["seller", "buyer"])).order_by(User.created_at.desc())
    count_query = select(func.count(User.id)).where(User.role.in_(["seller", "buyer"]))
    total = (await db.execute(count_query)).scalar() or 0

    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for u in rows:
        score = await compute_seller_score(db, u.id) if u.role == "seller" else None
        items.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "name": u.name,
            "country": u.country,
            "phone": u.phone,
            "uid": u.uid,
            "score": score,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return {"items": items, "total": total}


@router.delete("/users/batch")
async def delete_users_batch(
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not data.ids:
        return {"success": True, "deleted_count": 0}

    product_ids = select(Product.id).where(Product.seller_id.in_(data.ids))
    await db.execute(delete(Review).where(or_(Review.user_id.in_(data.ids), Review.product_id.in_(product_ids))))
    await db.execute(delete(SavedProduct).where(or_(SavedProduct.user_id.in_(data.ids), SavedProduct.product_id.in_(product_ids))))
    await db.execute(delete(SellerInquiry).where(or_(SellerInquiry.buyer_id.in_(data.ids), SellerInquiry.seller_id.in_(data.ids))))
    await db.execute(delete(Product).where(Product.seller_id.in_(data.ids)))
    result = await db.execute(delete(User).where(User.id.in_(data.ids), User.role.in_(["seller", "buyer"])))
    await db.commit()
    return {"success": True, "deleted_count": result.rowcount or 0}
