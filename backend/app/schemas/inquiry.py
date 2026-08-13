from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class InquiryCreate(BaseModel):
    raw_message: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_company: Optional[str] = None


class InquiryAnalysisResponse(BaseModel):
    id: int
    inquiry_id: int
    product_category: Optional[str] = None
    quantity: Optional[int] = None
    technical_params: Any = {}
    target_price: Optional[float] = None
    required_certifications: Any = []
    delivery_location: Optional[str] = None
    delivery_country: Optional[str] = None
    missing_info: Any = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InquiryResponse(BaseModel):
    id: int
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_company: Optional[str] = None
    raw_message: str
    analyses: list[InquiryAnalysisResponse] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MatchedProduct(BaseModel):
    product_id: int
    product_name: str
    sku: Optional[str] = None
    match_score: float
    match_reason: str
    moq: Optional[int] = None
    unit_price: Optional[float] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    pricing: Optional[str] = None
    lead_time_days: Optional[int] = None
    certifications: Optional[str] = None
    technical_specs: Optional[str] = None
    favorite_count: int = 0


class InquiryAnalysisResult(BaseModel):
    inquiry: InquiryResponse
    analysis: InquiryAnalysisResponse
    matched_products: list[MatchedProduct] = []
    ai_used: bool = False
