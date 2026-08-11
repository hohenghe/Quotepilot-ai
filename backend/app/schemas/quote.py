from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class QuoteGenerateRequest(BaseModel):
    inquiry_id: int
    selected_product_ids: list[int] = []
    additional_notes: Optional[str] = None


class QuoteResponse(BaseModel):
    id: int
    inquiry_id: Optional[int] = None
    subject: Optional[str] = None
    email_body: str
    matched_products: Any = []
    total_amount_low: Optional[float] = None
    total_amount_high: Optional[float] = None
    currency: str = "USD"
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
