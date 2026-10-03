from time import perf_counter
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import require_admin, require_auth, require_seller
from app.models.product import Product
from app.models.inquiry import Inquiry
from app.models.quote import Quote
from app.models.user import User
from app.models.seller_inquiry import SellerInquiry
from app.services.rating import compute_seller_scores

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/seller-home")
async def seller_home(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    """One small, authenticated response for the mini-program home screen."""
    started = perf_counter()
    product_count = (
        select(func.count(Product.id))
        .where(Product.seller_id == user.id, Product.is_active == True)
        .scalar_subquery()
    )
    counts = (await db.execute(
        select(
            product_count,
            func.count(SellerInquiry.id),
            func.count(SellerInquiry.id).filter(SellerInquiry.status == "pending"),
            func.count(SellerInquiry.id).filter(SellerInquiry.status == "replied"),
        ).where(SellerInquiry.seller_id == user.id)
    )).one()
    counts_done = perf_counter()
    recent = (await db.execute(
        select(
            SellerInquiry.id,
            SellerInquiry.buyer_email,
            SellerInquiry.status,
            SellerInquiry.raw_message,
        )
        .where(SellerInquiry.seller_id == user.id)
        .order_by(SellerInquiry.created_at.desc(), SellerInquiry.id.desc())
        .limit(5)
    )).all()
    recent_done = perf_counter()
    scores = await compute_seller_scores(db, [user.id])
    score_done = perf_counter()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Server-Timing"] = (
        f"counts;dur={(counts_done - started) * 1000:.1f}, "
        f"recent;dur={(recent_done - counts_done) * 1000:.1f}, "
        f"score;dur={(score_done - recent_done) * 1000:.1f}"
    )
    return {
        "email": user.email,
        "store_name": user.store_name,
        "name": user.name,
        "uid": user.uid,
        "product_count": counts[0] or 0,
        "inquiry_count": counts[1] or 0,
        "pending_count": counts[2] or 0,
        "replied_count": counts[3] or 0,
        "score": scores.get(user.id),
        "inquiries": [
            {
                "id": row.id,
                "buyer_email": row.buyer_email,
                "status": row.status,
                "raw_message": row.raw_message,
            }
            for row in recent
        ],
    }


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_auth),
):
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

    seller_ids = [s.id for s in sellers]
    product_counts = dict((await db.execute(
        select(Product.seller_id, func.count(Product.id))
        .where(Product.seller_id.in_(seller_ids), Product.is_active == True)
        .group_by(Product.seller_id)
    )).all()) if seller_ids else {}
    scores = await compute_seller_scores(db, seller_ids)

    items = []
    for s in sellers:
        items.append({
            "id": s.id,
            "email": s.email,
            "name": s.name,
            "product_count": product_counts.get(s.id, 0),
            "score": scores.get(s.id),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {"sellers": items}
