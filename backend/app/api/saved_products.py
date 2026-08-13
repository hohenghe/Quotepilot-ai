from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_buyer
from app.models.saved_product import SavedProduct
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/api/saved-products", tags=["saved-products"])


class SaveRequest(BaseModel):
    product_id: int


@router.post("")
async def save_product(
    data: SaveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_buyer),
):
    product = await db.get(Product, data.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = await db.execute(
        select(SavedProduct).where(
            SavedProduct.user_id == user.id,
            SavedProduct.product_id == data.product_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True}

    db.add(SavedProduct(user_id=user.id, product_id=data.product_id))
    await db.commit()
    return {"ok": True}


@router.get("")
async def list_saved(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_buyer),
):
    fav_subq = (
        select(func.count(SavedProduct.id))
        .where(SavedProduct.product_id == Product.id)
        .scalar_subquery()
    )
    stmt = (
        select(SavedProduct, Product, fav_subq.label("favorite_count"))
        .join(Product, SavedProduct.product_id == Product.id)
        .where(SavedProduct.user_id == user.id, Product.is_active == True)
        .order_by(SavedProduct.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    items = [
        {
            "product_id": p.id,
            "name": p.name,
            "sku": p.sku,
            "category": p.category,
            "moq": p.moq,
            "unit_price": p.unit_price,
            "price_range_low": p.price_range_low,
            "price_range_high": p.price_range_high,
            "pricing": p.pricing,
            "lead_time_days": p.lead_time_days,
            "certifications": p.certifications,
            "technical_specs": p.technical_specs,
            "favorite_count": fav or 0,
            "created_at": sp.created_at.isoformat() if sp.created_at else None,
        }
        for sp, p, fav in rows
    ]
    return {"items": items}


@router.delete("/{product_id}")
async def unsave_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_buyer),
):
    await db.execute(
        delete(SavedProduct).where(
            SavedProduct.user_id == user.id,
            SavedProduct.product_id == product_id,
        )
    )
    await db.commit()
    return {"ok": True}
