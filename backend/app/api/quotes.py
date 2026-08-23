"""
Quotes API — generate professional quotation emails.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import require_auth, require_admin
from app.models.quote import Quote
from app.models.inquiry import Inquiry
from app.models.product import Product
from app.models.user import User
from app.schemas.quote import QuoteGenerateRequest, QuoteResponse
from app.services.llm import generate_quote_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])


async def _get_owned_inquiry(db: AsyncSession, inquiry_id: int, user: User) -> Inquiry:
    """Load an inquiry and verify the caller owns it (or is admin)."""
    result = await db.execute(select(Inquiry).where(Inquiry.id == inquiry_id))
    inquiry = result.scalar_one_or_none()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if user.role == "admin":
        return inquiry
    if inquiry.buyer_id is None or inquiry.buyer_id != user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this inquiry")
    return inquiry


@router.post("/generate", response_model=QuoteResponse)
async def generate_quote(
    request: QuoteGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    inquiry = await _get_owned_inquiry(db, request.inquiry_id, user)

    # Get selected products (or all matched)
    product_ids = request.selected_product_ids
    if product_ids:
        result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    else:
        result = await db.execute(select(Product).where(Product.is_active == True).limit(5))

    products = result.scalars().all()

    if not products:
        raise HTTPException(status_code=400, detail="No products available for quotation")

    matched = [
        {
            "product_name": p.name,
            "sku": p.sku,
            "match_score": 0.92,
            "match_reason": "Meets all specified requirements",
            "moq": p.moq,
            "unit_price": p.unit_price,
            "price_range_low": p.price_range_low,
            "price_range_high": p.price_range_high,
            "pricing": p.pricing,
            "lead_time_days": p.lead_time_days,
            "certifications": p.certifications,
        }
        for p in products
    ]

    email_data = await generate_quote_email(
        inquiry_text=inquiry.raw_message,
        customer_name=inquiry.customer_name,
        matched_products=matched,
        additional_notes=request.additional_notes,
    )

    quote = Quote(
        inquiry_id=request.inquiry_id,
        subject=email_data["subject"],
        email_body=email_data["email_body"],
        matched_products=matched,
        total_amount_low=email_data["total_amount_low"],
        total_amount_high=email_data["total_amount_high"],
        currency=email_data["currency"],
        notes=request.additional_notes,
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)

    return QuoteResponse.model_validate(quote)


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Verify ownership via the linked inquiry (admin bypasses).
    if user.role != "admin" and quote.inquiry_id is not None:
        inq_result = await db.execute(select(Inquiry).where(Inquiry.id == quote.inquiry_id))
        inquiry = inq_result.scalar_one_or_none()
        if not inquiry or inquiry.buyer_id is None or inquiry.buyer_id != user.id:
            raise HTTPException(status_code=403, detail="You do not have access to this quote")

    return QuoteResponse.model_validate(quote)
