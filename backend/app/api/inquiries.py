import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_admin, require_auth, require_seller, require_buyer, get_current_user
from app.core.config import settings
from app.core.ratelimit import get_client_ip, rate_exceeded, get_analyze_semaphore
from app.models.inquiry import Inquiry, InquiryAnalysis
from app.models.product import Product
from app.models.user import User
from app.models.quote import Quote
from app.models.seller_inquiry import SellerInquiry
from app.models.saved_product import SavedProduct
from app.schemas.inquiry import (
    InquiryCreate,
    InquiryResponse,
    InquiryAnalysisResponse,
    InquiryAnalysisResult,
    MatchedProduct,
)
from app.services.llm import analyze_inquiry
from app.services.rag import search_products_hybrid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inquiries", tags=["inquiries"])


@router.get("", response_model=dict)
async def list_inquiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    query = select(Inquiry).order_by(Inquiry.created_at.desc())
    count_query = select(func.count(Inquiry.id))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    inquiries = result.scalars().all()

    items = [InquiryResponse.model_validate(i) for i in inquiries]
    return {"total": total, "items": items}


@router.get("/buyer", response_model=dict)
async def list_buyer_inquiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_buyer),
):
    count_query = select(func.count(SellerInquiry.id)).where(SellerInquiry.buyer_id == user.id)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    stmt = (
        select(SellerInquiry, Product.name, User.email, User.name, User.store_name)
        .outerjoin(Product, SellerInquiry.product_id == Product.id)
        .outerjoin(User, SellerInquiry.seller_id == User.id)
        .where(SellerInquiry.buyer_id == user.id)
        .order_by(SellerInquiry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        {
            "id": si.id,
            "product_id": si.product_id,
            "product_name": product_name,
            "seller_id": si.seller_id,
            "seller_name": seller_store or seller_name or seller_email,
            "seller_email": seller_email,
            "raw_message": si.raw_message,
            "status": si.status,
            "reply_body": si.reply_body,
            "created_at": si.created_at.isoformat() if si.created_at else None,
        }
        for si, product_name, seller_email, seller_name, seller_store in rows
    ]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": page * page_size < total,
    }


@router.post("/analyze", response_model=InquiryAnalysisResult)
async def analyze_and_match(
    data: InquiryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Anonymous-friendly inquiry analysis + product matching.

    Guest mode is preserved, but protected by:
      - per-IP rate limit (5/min) for guests, per-user (30/min) for logged-in
      - global concurrency cap (prevents DB-pool exhaustion under flood)
      - raw_message length cap (schema: max 4000 chars)

    Transaction boundary: AI analysis + vector search happen BEFORE any DB
    write, so no DB transaction is held open during the (potentially slow) LLM /
    embedding calls. If the LLM is configured but the call fails, a 503 is
    returned and NO Inquiry/Analysis row is created (no garbage records)."""
    # ── Rate limiting ──
    if user:
        rl_key = f"u:{user.id}"
        rl_limit = settings.ANALYZE_USER_RATE
    else:
        rl_key = f"ip:{get_client_ip(request)}"
        rl_limit = settings.ANALYZE_ANON_RATE
    if rate_exceeded(rl_key, rl_limit):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    async with get_analyze_semaphore():
        # ── 1. AI analysis (no DB transaction open) ──
        try:
            analysis_data = await analyze_inquiry(data.raw_message, raise_on_failure=True)
        except Exception:
            logger.warning("AI analysis failed for /analyze; returning 503 (no DB write)")
            raise HTTPException(
                status_code=503,
                detail="AI analysis service is temporarily unavailable. Please try again.",
            )

        # ── 2. Vector search (brief DB reads only, no write transaction) ──
        try:
            match_results = await search_products_hybrid(
                db, data.raw_message, top_k=5, embedding_max_retries=2
            )
        except Exception as e:
            logger.warning("Search failed, returning empty matches: %s", str(e)[:200])
            match_results = []

        # ── 3. Collect favorite counts (read-only, brief; non-critical) ──
        matched_ids = [mp["product_id"] for mp in match_results]
        fav_counts: dict[int, int] = {}
        if matched_ids:
            try:
                fav_rows = await db.execute(
                    select(SavedProduct.product_id, func.count(SavedProduct.id))
                    .where(SavedProduct.product_id.in_(matched_ids))
                    .group_by(SavedProduct.product_id)
                )
                fav_counts = {pid: cnt for pid, cnt in fav_rows.all()}
            except Exception:
                logger.warning("Favorite count query failed (non-critical)")

        # ── 4. Collect seller names (read-only, brief; non-critical) ──
        seller_ids = {mp.get("seller_id") for mp in match_results if mp.get("seller_id")}
        seller_names: dict[int, str] = {}
        if seller_ids:
            try:
                seller_rows = await db.execute(
                    select(User.id, User.name, User.email, User.store_name).where(User.id.in_(seller_ids))
                )
                seller_names = {sid: (store_name or name or email) for sid, name, email, store_name in seller_rows.all()}
            except Exception:
                logger.warning("Seller name query failed (non-critical)")

        # ── 5. Single short DB write transaction (INSERT inquiry + analysis, UPDATE view_count) ──
        try:
            inquiry = Inquiry(
                raw_message=data.raw_message,
                customer_name=data.customer_name,
                customer_email=data.customer_email,
                customer_company=data.customer_company,
                buyer_id=user.id if user else None,
            )
            db.add(inquiry)
            await db.flush()

            analysis = InquiryAnalysis(
                inquiry_id=inquiry.id,
                product_category=analysis_data["product_category"],
                quantity=analysis_data["quantity"],
                technical_params=analysis_data["technical_params"],
                target_price=analysis_data["target_price"],
                required_certifications=analysis_data["required_certifications"],
                delivery_location=analysis_data["delivery_location"],
                delivery_country=analysis_data["delivery_country"],
                missing_info=analysis_data["missing_info"],
            )
            db.add(analysis)

            if matched_ids:
                await db.execute(
                    update(Product)
                    .where(Product.id.in_(matched_ids))
                    .values(view_count=Product.view_count + 1)
                )

            await db.commit()
            await db.refresh(inquiry)
            await db.refresh(analysis)
            inquiry.analyses = [analysis]
        except Exception:
            logger.exception("DB write failed during /analyze")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again.",
            )

    # ── 6. Build response (pure in-memory, no DB) ──
    matched = []
    for mp in match_results:
        reasons = []
        if mp.get("category") == analysis_data.get("product_category"):
            reasons.append("Category matches inquiry requirements")
        if mp.get("certifications"):
            for cert in (analysis_data.get("required_certifications") or []):
                if cert.lower() in (mp.get("certifications") or "").lower():
                    reasons.append(f"{cert} certification confirmed")
                    break
        if not reasons:
            reasons.append("Product specifications align with your requirements")

        matched.append(
            MatchedProduct(
                product_id=mp["product_id"],
                product_name=mp["product_name"],
                seller_id=mp.get("seller_id"),
                seller_name=seller_names.get(mp.get("seller_id")),
                sku=mp.get("sku"),
                match_score=mp["match_score"],
                match_reason="; ".join(reasons),
                moq=mp.get("moq"),
                unit_price=mp.get("unit_price"),
                price_range_low=mp.get("price_range_low"),
                price_range_high=mp.get("price_range_high"),
                pricing=mp.get("pricing"),
                lead_time_days=mp.get("lead_time_days"),
                certifications=mp.get("certifications"),
                technical_specs=mp.get("technical_specs"),
                favorite_count=fav_counts.get(mp["product_id"], 0),
            )
        )

    return InquiryAnalysisResult(
        inquiry=InquiryResponse.model_validate(inquiry),
        analysis=InquiryAnalysisResponse.model_validate(analysis),
        matched_products=matched,
        ai_used=analysis_data.get("ai_used", False),
    )


@router.get("/admin/all", response_model=dict)
async def admin_list_inquiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(Inquiry).order_by(Inquiry.created_at.desc())
    count_query = select(func.count(Inquiry.id))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    inquiries = result.scalars().all()

    items = [InquiryResponse.model_validate(i) for i in inquiries]
    return {"total": total, "items": items}


class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.delete("/batch")
async def delete_inquiries_batch(
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not data.ids:
        return {"success": True, "deleted_count": 0}

    await db.execute(delete(SellerInquiry).where(SellerInquiry.inquiry_id.in_(data.ids)))
    await db.execute(delete(Quote).where(Quote.inquiry_id.in_(data.ids)))
    await db.execute(delete(InquiryAnalysis).where(InquiryAnalysis.inquiry_id.in_(data.ids)))
    result = await db.execute(delete(Inquiry).where(Inquiry.id.in_(data.ids)))
    await db.commit()
    return {"success": True, "deleted_count": result.rowcount or 0}
