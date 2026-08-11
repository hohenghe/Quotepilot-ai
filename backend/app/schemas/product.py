from pydantic import BaseModel, Field
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
    lead_time_days: Optional[int] = None
    image_url: Optional[str] = None


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
    lead_time_days: Optional[int] = None
    image_url: Optional[str] = None
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
    lead_time_days: Optional[int] = None
    image_url: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

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
