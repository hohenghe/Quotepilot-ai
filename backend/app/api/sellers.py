from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import require_seller, get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.saved_product import SavedProduct
from app.schemas.product import ProductResponse
from app.services.rating import compute_seller_score

router = APIRouter(prefix="/api/sellers", tags=["sellers"])


@router.get("/score")
async def seller_score(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    score = await compute_seller_score(db, user.id)
    return {"score": score}


@router.get("/{seller_id}/products")
async def seller_products(
    seller_id: int,
    db: AsyncSession = Depends(get_db),
    caller: User | None = Depends(get_current_user),
):
    """Public listing of a seller's active products (for buyers to browse).

    Anonymous callers see only the store/display name — the seller's email is
    NOT exposed to unauthenticated users (PII protection). Authenticated users
    still receive it (used as a display fallback in the buyer inquiries list)."""
    seller = await db.get(User, seller_id)
    if not seller or seller.role != "seller":
        raise HTTPException(status_code=404, detail="Seller not found")

    is_anon = caller is None
    # Anonymous: store_name or name only (never email as a name fallback).
    # Authenticated: store_name or name or email (preserves existing behavior).
    display_name = seller.store_name or seller.name
    if not is_anon and not display_name:
        display_name = seller.email
    exposed_email = None if is_anon else seller.email

    fav_subq = (
        select(func.count(SavedProduct.id))
        .where(SavedProduct.product_id == Product.id)
        .scalar_subquery()
    )
    stmt = (
        select(Product, fav_subq.label("favorite_count"))
        .where(Product.seller_id == seller_id, Product.is_active == True)
        .order_by(Product.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for p, fav in rows:
        resp = ProductResponse.model_validate(p)
        resp.favorite_count = fav or 0
        resp.seller_name = display_name
        resp.seller_email = exposed_email
        items.append(resp)

    score = await compute_seller_score(db, seller_id)
    return {
        "seller_id": seller_id,
        "seller_name": display_name,
        "seller_email": exposed_email,
        "score": score,
        "items": items,
    }
