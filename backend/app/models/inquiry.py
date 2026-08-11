from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String(200), nullable=True)
    customer_email = Column(String(300), nullable=True)
    customer_company = Column(String(300), nullable=True)
    raw_message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analyses = relationship("InquiryAnalysis", back_populates="inquiry", cascade="all, delete-orphan")


class InquiryAnalysis(Base):
    __tablename__ = "inquiry_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False)
    product_category = Column(String(200), nullable=True)
    quantity = Column(Integer, nullable=True)
    technical_params = Column(JSON, default=dict)
    target_price = Column(Float, nullable=True)
    required_certifications = Column(JSON, default=list)
    delivery_location = Column(String(300), nullable=True)
    delivery_country = Column(String(100), nullable=True)
    missing_info = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inquiry = relationship("Inquiry", back_populates="analyses")
