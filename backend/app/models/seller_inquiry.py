from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class SellerInquiry(Base):
    __tablename__ = "seller_inquiries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    raw_message = Column(Text, nullable=False)
    buyer_email = Column(String(300), nullable=True)
    status = Column(String(20), default="pending")  # pending | replied
    reply_body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
