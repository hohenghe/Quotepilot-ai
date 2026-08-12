from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import require_seller, require_auth
from app.models.seller_inquiry import SellerInquiry
from app.models.user import User
from app.services.llm import generate_quote_email
from app.models.product import Product

router = APIRouter(prefix="/api/seller-inquiries", tags=["seller-inquiries"])


class SendInquiryRequest(BaseModel):
    inquiry_text: str
    product_id: int
    buyer_email: str | None = None


@router.post("/send")
async def send_inquiry(
    data: SendInquiryRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_auth),
):
    # Find the product and its seller
    result = await db.execute(select(Product).where(Product.id == data.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.seller_id:
        raise HTTPException(status_code=400, detail="Product has no seller")

    inquiry = SellerInquiry(
        buyer_id=user.id if user else None,
        seller_id=product.seller_id,
        product_id=data.product_id,
        raw_message=data.inquiry_text,
        buyer_email=data.buyer_email or (user.email if user else None),
    )
    db.add(inquiry)
    await db.commit()
    await db.refresh(inquiry)
    return {"ok": True, "id": inquiry.id}


@router.get("/received")
async def list_received(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    query = (
        select(SellerInquiry)
        .where(SellerInquiry.seller_id == user.id)
        .order_by(SellerInquiry.created_at.desc())
    )
    count_query = select(func.count(SellerInquiry.id)).where(SellerInquiry.seller_id == user.id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": i.id,
                "raw_message": i.raw_message,
                "buyer_email": i.buyer_email,
                "product_id": i.product_id,
                "status": i.status,
                "reply_body": i.reply_body,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
    }


class GenerateReplyRequest(BaseModel):
    inquiry_id: int


@router.post("/generate-reply")
async def generate_reply(
    data: GenerateReplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_seller),
):
    result = await db.execute(
        select(SellerInquiry).where(
            SellerInquiry.id == data.inquiry_id,
            SellerInquiry.seller_id == user.id,
        )
    )
    inquiry = result.scalar_one_or_none()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    # Get product info
    product = None
    matched_products = []
    if inquiry.product_id:
        p_result = await db.execute(select(Product).where(Product.id == inquiry.product_id))
        product = p_result.scalar_one_or_none()
        if product:
            matched_products = [{
                "product_name": product.name,
                "sku": product.sku,
                "match_score": 1.0,
                "match_reason": "Customer selected this product",
                "moq": product.moq,
                "unit_price": product.unit_price,
                "price_range_low": product.price_range_low,
                "price_range_high": product.price_range_high,
                "pricing": product.pricing,
                "lead_time_days": product.lead_time_days,
                "certifications": product.certifications,
            }]

    email_data = await generate_quote_email(
        inquiry_text=inquiry.raw_message,
        customer_name=inquiry.buyer_email,
        matched_products=matched_products,
    )

    inquiry.reply_body = email_data["email_body"]
    inquiry.status = "replied"
    await db.commit()

    return {
        "subject": email_data["subject"],
        "email_body": email_data["email_body"],
    }
