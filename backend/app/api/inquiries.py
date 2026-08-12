from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import require_admin, require_auth, require_seller
from app.models.inquiry import Inquiry, InquiryAnalysis
from app.models.product import Product
from app.models.user import User
from app.models.quote import Quote
from app.schemas.inquiry import (
    InquiryCreate,
    InquiryResponse,
    InquiryAnalysisResponse,
    InquiryAnalysisResult,
    MatchedProduct,
)
from app.services.llm import analyze_inquiry
from app.services.rag import search_products_hybrid

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


@router.post("/analyze", response_model=InquiryAnalysisResult)
async def analyze_and_match(request: InquiryCreate, db: AsyncSession = Depends(get_db)):
    inquiry = Inquiry(
        raw_message=request.raw_message,
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        customer_company=request.customer_company,
    )
    db.add(inquiry)
    await db.flush()

    analysis_data = await analyze_inquiry(request.raw_message)
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
    await db.commit()
    await db.refresh(inquiry)
    await db.refresh(analysis)
    inquiry.analyses = [analysis]

    result = await db.execute(
        select(Product).where(Product.is_active == True)
    )
    all_products = result.scalars().all()

    if all_products:
        product_dicts = [
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "category": p.category,
                "description": p.description,
                "technical_specs": p.technical_specs,
                "certifications": p.certifications,
                "moq": p.moq,
                "unit_price": p.unit_price,
                "price_range_low": p.price_range_low,
                "price_range_high": p.price_range_high,
                "pricing": p.pricing,
                "lead_time_days": p.lead_time_days,
            }
            for p in all_products
        ]

        matches = await search_products_hybrid(request.raw_message, product_dicts, top_k=5)
        matched = []
        for p, score in matches:
            reasons = []
            if p.get("category") == analysis_data.get("product_category"):
                reasons.append("Category matches inquiry requirements")
            if p.get("certifications"):
                for cert in (analysis_data.get("required_certifications") or []):
                    if cert.lower() in (p.get("certifications") or "").lower():
                        reasons.append(f"{cert} certification confirmed")
                        break
            if not reasons:
                reasons.append("Product specifications align with your requirements")

            matched.append(
                MatchedProduct(
                    product_id=p["id"],
                    product_name=p["name"],
                    sku=p.get("sku"),
                    match_score=round(score, 3),
                    match_reason="; ".join(reasons),
                    moq=p.get("moq"),
                    unit_price=p.get("unit_price"),
                    price_range_low=p.get("price_range_low"),
                    price_range_high=p.get("price_range_high"),
                    pricing=p.get("pricing"),
                    lead_time_days=p.get("lead_time_days"),
                    certifications=p.get("certifications"),
                    technical_specs=p.get("technical_specs"),
                )
            )
    else:
        matched = []

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
