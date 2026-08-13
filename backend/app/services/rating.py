from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.models.review import Review
from app.models.seller_inquiry import SellerInquiry


async def compute_product_rating(db: AsyncSession, product_id: int) -> float | None:
    avg = (await db.execute(
        select(func.avg(Review.rating)).where(Review.product_id == product_id)
    )).scalar()
    return round(float(avg), 1) if avg is not None else None


async def compute_seller_score(db: AsyncSession, seller_id: int) -> float | None:
    """Weighted average of the seller's product ratings, weighted by inquiry volume."""
    product_ids = (await db.execute(
        select(Product.id).where(Product.seller_id == seller_id, Product.is_active == True)
    )).scalars().all()

    weighted_sum = 0.0
    total_weight = 0.0
    for pid in product_ids:
        avg = (await db.execute(
            select(func.avg(Review.rating)).where(Review.product_id == pid)
        )).scalar()
        score = float(avg) if avg is not None else 0.0
        cnt = (await db.execute(
            select(func.count(SellerInquiry.id)).where(SellerInquiry.product_id == pid)
        )).scalar() or 0
        weighted_sum += score * cnt
        total_weight += cnt

    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 1)
