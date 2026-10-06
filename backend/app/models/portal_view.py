from sqlalchemy import Column, Date, Integer, String

from app.core.database import Base


class PortalDailyView(Base):
    __tablename__ = "portal_daily_views"

    day = Column(Date, primary_key=True)
    portal = Column(String(20), primary_key=True)
    views = Column(Integer, nullable=False, default=0)
