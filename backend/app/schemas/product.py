from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category: str = "other"
    description: Optional[str] = None
    technical_specs: Optional[str] = None
    certifications: Optional[str] = None
    moq: Optional[int] = None
    unit_price: Optional[float] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    pricing: Optional[str] = None
    lead_time_days: Optional[int] = None
    image_url: Optional[str] = None
    images: list[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    technical_specs: Optional[str] = None
    certifications: Optional[str] = None
    moq: Optional[int] = None
    unit_price: Optional[float] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    pricing: Optional[str] = None
    lead_time_days: Optional[int] = None
    image_url: Optional[str] = None
    images: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: Optional[str] = None
    category: str
    description: Optional[str] = None
    technical_specs: Optional[str] = None
    certifications: Optional[str] = None
    moq: Optional[int] = None
    unit_price: Optional[float] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    pricing: Optional[str] = None
    lead_time_days: Optional[int] = None
    image_url: Optional[str] = None
    images: list[str] = []
    is_active: bool
    view_count: int = 0
    favorite_count: int = 0
    created_at: Optional[datetime] = None
    seller_name: Optional[str] = None
    seller_email: Optional[str] = None

    @field_validator("images", mode="before")
    @classmethod
    def _coerce_images(cls, v):
        return v if v is not None else []

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    total: int
    items: list[ProductResponse]


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    products_count: int
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
