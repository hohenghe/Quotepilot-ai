from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_auth, require_buyer, require_seller, require_admin
from app.models.review import Review
from app.models.user import User
from app.services.rating import compute_seller_score

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class CreateReviewRequest(BaseModel):
    seller_id: int
    rating: float
    content: str | None = None
    images: list[str] = []


def _serialize(review: Review, user_name: str | None, user_email: str | None) -> dict:
    return {
        "id": review.id,
        "seller_id": review.seller_id,
        "user_id": review.user_id,
        "user_name": user_name or user_email,
        "rating": review.rating,
        "content": review.content,
        "images": review.images or [],
        "reported": review.reported,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


@router.post("")
async def create_review(
    data: CreateReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_buyer),
):
    rating = round(data.rating, 1)
    if rating < 0 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

    seller = await db.get(User, data.seller_id)
    if not seller or seller.role != "seller":
        raise HTTPException(status_code=404, detail="Seller not found")

    existing = (await db.execute(
        select(Review).where(Review.seller_id == data.seller_id, Review.user_id == user.id)
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
        seller_id=data.seller_id,
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
    seller_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_auth),
):
    stmt = (
        select(Review, User.name, User.email)
        .join(User, Review.user_id == User.id)
        .where(Review.seller_id == seller_id)
        .order_by(Review.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [_serialize(r, name, email) for r, name, email in rows]
    score = await compute_seller_score(db, seller_id)
    return {"items": items, "score": score, "review_count": len(items)}


@router.get("/seller")
async def list_seller_reviews(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    stmt = (
        select(Review, User.name, User.email)
        .join(User, Review.user_id == User.id)
        .where(Review.seller_id == user.id)
        .order_by(Review.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [_serialize(r, name, email) for r, name, email in rows]
    score = await compute_seller_score(db, user.id)
    return {"items": items, "score": score}


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
    seller = aliased(User)
    stmt = (
        select(Review, User.name, User.email, seller.name, seller.email, seller.store_name)
        .join(User, Review.user_id == User.id)
        .join(seller, Review.seller_id == seller.id)
        .order_by(Review.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = []
    for r, user_name, user_email, seller_name, seller_email, seller_store in rows:
        item = _serialize(r, user_name, user_email)
        item["seller_name"] = seller_store or seller_name
        item["seller_email"] = seller_email
        items.append(item)
    return {"items": items}
