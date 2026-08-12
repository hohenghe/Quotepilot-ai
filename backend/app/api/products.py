"""
Products API — CRUD operations for product catalog.
"""
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.product import Product
from app.models.document import Document
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse, DocumentResponse
from app.services.file_parser import parse_file

router = APIRouter(prefix="/api/products", tags=["products"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).where(Product.is_active == True)
    count_query = select(func.count(Product.id)).where(Product.is_active == True)

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
    items = result.scalars().all()

    return ProductListResponse(
        total=total,
        items=[ProductResponse.model_validate(p) for p in items],
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.post("/upload", response_model=DocumentResponse)
async def upload_product_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    allowed_exts = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".csv"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        filename=file.filename,
        file_type=ext[1:],
        file_path=file_path,
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
async def update_product(product_id: int, data: ProductUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    await db.commit()
    return {"ok": True}


@router.get("/stats/summary")
async def product_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count(Product.id)).where(Product.is_active == True))
    total = total_result.scalar() or 0

    cat_result = await db.execute(
        select(Product.category, func.count(Product.id))
        .where(Product.is_active == True)
        .group_by(Product.category)
    )
    categories = {row[0]: row[1] for row in cat_result.fetchall()}

    return {"total_products": total, "categories": categories}
