import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from pydantic import BaseModel
from typing import List
from app.core.database import get_db
from app.core.auth import require_seller, require_admin, get_current_user, require_auth
from app.models.product import Product
from app.models.document import Document
from app.models.user import User
from app.models.saved_product import SavedProduct
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse, DocumentResponse
from app.services.file_parser import parse_file
from app.services.storage import get_storage

router = APIRouter(prefix="/api/products", tags=["products"])


def _scope_by_seller(query, user: User):
    return query.where(Product.seller_id == user.id)


def _favorite_count_subquery():
    return (
        select(func.count(SavedProduct.id))
        .where(SavedProduct.product_id == Product.id)
        .scalar_subquery()
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=2000),
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    query = select(Product, _favorite_count_subquery().label("favorite_count")).where(Product.is_active == True)
    count_query = select(func.count(Product.id)).where(Product.is_active == True)

    if user:
        query = _scope_by_seller(query, user)
        count_query = _scope_by_seller(count_query, user)

    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
        count_query = count_query.where(Product.name.ilike(f"%{search}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Product.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    items = []
    for p, fav in rows:
        resp = ProductResponse.model_validate(p)
        resp.favorite_count = fav or 0
        items.append(resp)

    return ProductListResponse(
        total=total,
        items=items,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product, _favorite_count_subquery().label("favorite_count")).where(Product.id == product_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    product, fav = row
    resp = ProductResponse.model_validate(product)
    resp.favorite_count = fav or 0
    return resp


@router.post("/upload", response_model=DocumentResponse)
async def upload_product_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    allowed_exts = {".pdf", ".xlsx", ".docx", ".csv"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    storage_key = await get_storage().save(file.filename or "", content)

    doc = Document(
        filename=file.filename,
        file_type=ext[1:],
        file_path=storage_key,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        parsed_products = await parse_file(file.filename or "", content)
        for pdata in parsed_products:
            product = Product(
                name=pdata["name"],
                sku=pdata.get("sku"),
                category=pdata.get("category", "other"),
                description=pdata.get("description"),
                technical_specs=pdata.get("technical_specs"),
                certifications=pdata.get("certifications"),
                moq=pdata.get("moq"),
                unit_price=pdata.get("unit_price"),
                price_range_low=pdata.get("price_range_low"),
                price_range_high=pdata.get("price_range_high"),
                pricing=pdata.get("pricing"),
                lead_time_days=pdata.get("lead_time_days"),
                seller_id=user.id,
            )
            db.add(product)

        doc.status = "completed"
        doc.products_count = len(parsed_products)
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        await db.commit()
        await db.refresh(doc)

    return DocumentResponse.model_validate(doc)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int, data: ProductUpdate, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.seller_id == user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


class BatchDeleteRequest(BaseModel):
    product_ids: List[int]


@router.delete("/batch")
async def delete_products_batch(
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Bulk soft-delete products. Sellers are scoped to their own products;
    admins may delete any product. One HTTP request, one bulk UPDATE, one commit."""
    if user.role not in ("seller", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    ids = data.product_ids
    if not ids:
        return {"success": True, "deleted_count": 0}

    # Chunk to avoid exceeding DB IN(...) parameter limits
    chunk_size = 500
    deleted_count = 0
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i + chunk_size]
        stmt = update(Product).where(
            Product.id.in_(chunk),
            Product.is_active == True,
        )
        if user.role == "seller":
            stmt = stmt.where(Product.seller_id == user.id)
        result = await db.execute(
            stmt.values(is_active=False, embedding_status="skipped")
        )
        deleted_count += result.rowcount or 0

    await db.commit()
    return {"success": True, "deleted_count": deleted_count}


@router.delete("/all")
async def delete_all_products(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    """Bulk soft-delete ALL active products owned by the current seller."""
    result = await db.execute(
        update(Product)
        .where(Product.seller_id == user.id, Product.is_active == True)
        .values(is_active=False, embedding_status="skipped")
    )
    await db.commit()
    return {"success": True, "deleted_count": result.rowcount or 0}


@router.delete("/{product_id}")
async def delete_product(
    product_id: int, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.seller_id == user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    product.embedding_status = "skipped"
    await db.commit()
    return {"ok": True, "id": product_id, "is_active": False}


@router.get("/stats/summary")
async def product_stats(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    base = select(func.count(Product.id)).where(Product.is_active == True)
    if user:
        base = base.where(Product.seller_id == user.id)
    total_result = await db.execute(base)
    total = total_result.scalar() or 0

    cat_base = (
        select(Product.category, func.count(Product.id))
        .where(Product.is_active == True)
    )
    if user:
        cat_base = cat_base.where(Product.seller_id == user.id)
    cat_result = await db.execute(cat_base.group_by(Product.category))
    categories = {row[0]: row[1] for row in cat_result.fetchall()}

    return {"total_products": total, "categories": categories}


@router.get("/admin/all", response_model=ProductListResponse)
async def admin_list_all_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=2000),
    search: str | None = None,
    seller_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = (
        select(Product, User.name, User.email, User.store_name, _favorite_count_subquery().label("favorite_count"))
        .outerjoin(User, Product.seller_id == User.id)
        .where(Product.is_active == True)
    )
    count_query = select(func.count(Product.id)).where(Product.is_active == True)

    if seller_id:
        query = query.where(Product.seller_id == seller_id)
        count_query = count_query.where(Product.seller_id == seller_id)
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
        count_query = count_query.where(Product.name.ilike(f"%{search}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Product.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    items = []
    for p, seller_name, seller_email, seller_store, fav in rows:
        resp = ProductResponse.model_validate(p)
        resp.seller_name = seller_store or seller_name
        resp.seller_email = seller_email
        resp.favorite_count = fav or 0
        items.append(resp)

    return ProductListResponse(
        total=total,
        items=items,
    )
