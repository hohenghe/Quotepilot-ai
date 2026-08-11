from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class ProductCategory(str, enum.Enum):
    led_lighting = "led_lighting"
    electronics = "electronics"
    machinery = "machinery"
    textiles = "textiles"
    furniture = "furniture"
    packaging = "packaging"
    auto_parts = "auto_parts"
    hardware = "hardware"
    other = "other"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    sku = Column(String(100), unique=True, nullable=True)
    category = Column(String(100), nullable=False, default="other")
    description = Column(Text, nullable=True)
    technical_specs = Column(Text, nullable=True)
    certifications = Column(String(500), nullable=True)
    moq = Column(Integer, nullable=True)
    unit_price = Column(Float, nullable=True)
    price_range_low = Column(Float, nullable=True)
    price_range_high = Column(Float, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
