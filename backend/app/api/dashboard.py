from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import require_admin, require_seller
from app.models.product import Product
from app.models.inquiry import Inquiry
from app.models.quote import Quote
from app.models.user import User
from app.services.rating import compute_seller_score

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count(Product.id)).where(Product.is_active == True))
    total_products = total_result.scalar() or 0

    from sqlalchemy import text
    today_result = await db.execute(
        select(func.count(Inquiry.id)).where(
            func.date(Inquiry.created_at) == func.current_date()
        )
    )
    today_inquiries = today_result.scalar() or 0

    total_inq_result = await db.execute(select(func.count(Inquiry.id)))
    total_inquiries = total_inq_result.scalar() or 0

    total_quo_result = await db.execute(select(func.count(Quote.id)))
    total_quotes = total_quo_result.scalar() or 0

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


@router.get("/admin")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    total_products = (await db.execute(
        select(func.count(Product.id)).where(Product.is_active == True)
    )).scalar() or 0

    total_inquiries = (await db.execute(
        select(func.count(Inquiry.id))
    )).scalar() or 0

    total_quotes = (await db.execute(
        select(func.count(Quote.id))
    )).scalar() or 0

    total_sellers = (await db.execute(
        select(func.count(User.id)).where(User.role == "seller", User.is_active == True)
    )).scalar() or 0

    cat_result = await db.execute(
        select(Product.category, func.count(Product.id))
        .where(Product.is_active == True)
        .group_by(Product.category)
    )
    categories = {row[0]: row[1] for row in cat_result.fetchall()}

    return {
        "total_products": total_products,
        "total_inquiries": total_inquiries,
        "total_quotes": total_quotes,
        "total_sellers": total_sellers,
        "categories": categories,
    }


@router.get("/admin/sellers")
async def admin_list_sellers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).where(User.role == "seller", User.is_active == True)
    )
    sellers = result.scalars().all()

    items = []
    for s in sellers:
        product_count = (await db.execute(
            select(func.count(Product.id)).where(
                Product.seller_id == s.id, Product.is_active == True
            )
        )).scalar() or 0
        score = await compute_seller_score(db, s.id)
        items.append({
            "id": s.id,
            "email": s.email,
            "name": s.name,
            "product_count": product_count,
            "score": score,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {"sellers": items}
