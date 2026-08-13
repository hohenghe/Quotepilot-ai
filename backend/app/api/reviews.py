from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_auth, require_buyer, require_seller, require_admin
from app.models.review import Review
from app.models.product import Product
from app.models.user import User
from app.services.rating import compute_product_rating

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class CreateReviewRequest(BaseModel):
    product_id: int
    rating: float
    content: str | None = None
    images: list[str] = []


@router.post("")
async def create_review(
    data: CreateReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_buyer),
):
    rating = round(data.rating, 1)
    if rating < 0 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

    product = await db.get(Product, data.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (await db.execute(
        select(Review).where(Review.product_id == data.product_id, Review.user_id == user.id)
    )).scalar_one_or_none()

    if existing:
        existing.rating = rating
        existing.content = (data.content or "").strip() or None
        existing.images = data.images
        existing.reported = False
        await db.commit()
        await db.refresh(existing)
        return {"ok": True, "id": existing.id}

    review = Review(
        product_id=data.product_id,
        seller_id=product.seller_id,
        user_id=user.id,
        rating=rating,
        content=(data.content or "").strip() or None,
        images=data.images,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return {"ok": True, "id": review.id}


@router.get("")
async def list_reviews(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_auth),
):
    stmt = (
        select(Review, User.name, User.email)
        .join(User, Review.user_id == User.id)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name": name or email,
            "rating": r.rating,
            "content": r.content,
            "images": r.images or [],
            "reported": r.reported,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, name, email in rows
    ]
    rating = await compute_product_rating(db, product_id)
    return {"items": items, "rating": rating, "review_count": len(items)}


@router.get("/seller")
async def list_seller_reviews(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    stmt = (
        select(Review, Product.name, User.email)
        .join(Product, Review.product_id == Product.id)
        .join(User, Review.user_id == User.id)
        .where(Review.seller_id == user.id)
        .order_by(Review.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [
        {
            "id": r.id,
            "product_id": r.product_id,
            "product_name": product_name,
            "user_id": r.user_id,
            "user_email": email,
            "rating": r.rating,
            "content": r.content,
            "images": r.images or [],
            "reported": r.reported,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, product_name, email in rows
    ]
    return {"items": items}


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if user.role != "admin" and review.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await db.delete(review)
    await db.commit()
    return {"ok": True}


@router.post("/{review_id}/report")
async def report_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.seller_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    review.reported = True
    await db.commit()
    return {"ok": True}


@router.get("/admin/all")
async def admin_list_reviews(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = (
        select(Review, Product.name, User.email)
        .join(Product, Review.product_id == Product.id)
        .join(User, Review.user_id == User.id)
        .order_by(Review.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [
        {
            "id": r.id,
            "product_id": r.product_id,
            "product_name": product_name,
            "user_id": r.user_id,
            "user_email": email,
            "rating": r.rating,
            "content": r.content,
            "images": r.images or [],
            "reported": r.reported,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, product_name, email in rows
    ]
    return {"items": items}
