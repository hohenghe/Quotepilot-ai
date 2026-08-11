"""
Dashboard API — summary statistics for the dashboard page.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.product import Product
from app.models.inquiry import Inquiry
from app.models.quote import Quote

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    # Product count
    total_result = await db.execute(select(func.count(Product.id)).where(Product.is_active == True))
    total_products = total_result.scalar() or 0

    # Today's inquiries
    from sqlalchemy import text
    today_result = await db.execute(
        select(func.count(Inquiry.id)).where(
            func.date(Inquiry.created_at) == func.current_date()
        )
    )
    today_inquiries = today_result.scalar() or 0

    # Total inquiries
    total_inq_result = await db.execute(select(func.count(Inquiry.id)))
    total_inquiries = total_inq_result.scalar() or 0

    # Total quotes generated
    total_quo_result = await db.execute(select(func.count(Quote.id)))
    total_quotes = total_quo_result.scalar() or 0

    # Category breakdown
    cat_result = await db.execute(
        select(Product.category, func.count(Product.id))
        .where(Product.is_active == True)
        .group_by(Product.category)
    )
    categories = {row[0]: row[1] for row in cat_result.fetchall()}

    return {
        "total_products": total_products,
        "today_inquiries": today_inquiries,
        "total_inquiries": total_inquiries,
        "total_quotes": total_quotes,
        "categories": categories,
    }
