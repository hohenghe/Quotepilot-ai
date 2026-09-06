import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_admin
from app.models.user import User
from app.models.product import Product
from app.models.inquiry import Inquiry, InquiryAnalysis
from app.models.quote import Quote
from app.models.seller_inquiry import SellerInquiry
from app.models.saved_product import SavedProduct
from app.models.review import Review
from app.services.rating import compute_seller_score
from app.core.config import is_llm_available
from app.services.email import send_verification_email
from app.services.llm import analyze_inquiry

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


class BatchDeleteRequest(BaseModel):
    ids: list[int]


class TestEmailRequest(BaseModel):
    email: str


class TestLlmRequest(BaseModel):
    prompt: str


class TestProductDeleteRequest(BaseModel):
    product_id: int


TEST_PRODUCT_SKU_PREFIX = "ADMIN-TEST-"


@router.delete("/reset")
async def reset_all(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """Admin: delete all inquiries, products, and seller/buyer accounts (in FK-safe order)."""
    await db.execute(delete(SellerInquiry))
    await db.execute(delete(Quote))
    await db.execute(delete(InquiryAnalysis))
    await db.execute(delete(Inquiry))
    await db.execute(delete(Review))
    await db.execute(delete(SavedProduct))
    await db.execute(delete(Product))
    await db.execute(delete(User).where(User.role.in_(["seller", "buyer"])))
    await db.commit()
    return {"ok": True}


@router.delete("/saved-products")
async def clear_saved_products(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """Admin: clear every buyer's saved products (reset the favorites state)."""
    result = await db.execute(delete(SavedProduct))
    await db.commit()
    return {"success": True, "deleted_count": result.rowcount or 0}


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(User).where(User.role.in_(["seller", "buyer"])).order_by(User.created_at.desc())
    count_query = select(func.count(User.id)).where(User.role.in_(["seller", "buyer"]))
    total = (await db.execute(count_query)).scalar() or 0

    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for u in rows:
        score = await compute_seller_score(db, u.id) if u.role == "seller" else None
        items.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "name": u.name,
            "country": u.country,
            "phone": u.phone,
            "uid": u.uid,
            "score": score,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return {"items": items, "total": total}


@router.delete("/users/batch")
async def delete_users_batch(
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not data.ids:
        return {"success": True, "deleted_count": 0}

    product_ids = select(Product.id).where(Product.seller_id.in_(data.ids))
    await db.execute(delete(Review).where(or_(Review.user_id.in_(data.ids), Review.seller_id.in_(data.ids))))
    await db.execute(delete(SavedProduct).where(or_(SavedProduct.user_id.in_(data.ids), SavedProduct.product_id.in_(product_ids))))
    await db.execute(delete(SellerInquiry).where(or_(SellerInquiry.buyer_id.in_(data.ids), SellerInquiry.seller_id.in_(data.ids))))
    await db.execute(delete(Product).where(Product.seller_id.in_(data.ids)))
    result = await db.execute(delete(User).where(User.id.in_(data.ids), User.role.in_(["seller", "buyer"])))
    await db.commit()
    return {"success": True, "deleted_count": result.rowcount or 0}


@router.post("/tests/verification-email")
async def test_verification_email(
    data: TestEmailRequest,
    _: User = Depends(require_admin),
):
    """Send a delivery-only verification email test without touching accounts/tokens."""
    email = data.email.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Please enter a valid email address")

    # This token intentionally is not stored: the email checks Brevo delivery
    # and rendering only, and cannot change an account if clicked.
    sent = await send_verification_email(email, "admin-delivery-test")
    if not sent:
        raise HTTPException(status_code=502, detail="Verification email was not sent. Check the mail configuration and delivery logs.")
    return {"success": True, "message": "Test verification email sent. Its link is intentionally not valid for account verification."}


@router.post("/tests/llm")
async def test_llm(
    data: TestLlmRequest,
    _: User = Depends(require_admin),
):
    """Exercise the configured LLM with the production inquiry-analysis prompt."""
    prompt = data.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Please enter a test prompt")
    if len(prompt) > 2000:
        raise HTTPException(status_code=422, detail="Test prompt must be 2000 characters or fewer")
    if not is_llm_available():
        raise HTTPException(status_code=503, detail="LLM is not configured")

    try:
        result = await analyze_inquiry(prompt, raise_on_failure=True)
    except Exception:
        logger.exception("Admin LLM test failed")
        raise HTTPException(status_code=502, detail="LLM call failed. Check the model configuration and server logs.")
    return {"success": True, "ai_used": bool(result.get("ai_used")), "analysis": result}


@router.post("/tests/products")
async def create_test_product(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create an inactive, admin-owned product exclusively for CRUD testing."""
    suffix = uuid4().hex[:10].upper()
    product = Product(
        name=f"[TEST] Admin product {suffix}",
        sku=f"{TEST_PRODUCT_SKU_PREFIX}{suffix}",
        category="other",
        description="Created by the admin test console. This inactive product is excluded from buyer search.",
        seller_id=admin.id,
        is_active=False,
        embedding_status="skipped",
        images=[],
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return {"success": True, "product_id": product.id, "name": product.name, "sku": product.sku}


@router.delete("/tests/products")
async def delete_test_product(
    data: TestProductDeleteRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Hard-delete only a test product created by the same admin."""
    product = (await db.execute(
        select(Product).where(Product.id == data.product_id, Product.seller_id == admin.id)
    )).scalar_one_or_none()
    if not product or not (product.sku or "").startswith(TEST_PRODUCT_SKU_PREFIX):
        raise HTTPException(status_code=404, detail="Admin test product not found")
    await db.delete(product)
    await db.commit()
    return {"success": True, "deleted_product_id": data.product_id}
