"""Small daily counters for web portal visits and admin trend queries."""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_admin
from app.core.config import get_cors_origins
from app.core.database import get_db
from app.core.ratelimit import get_client_ip, rate_exceeded
from app.models.inquiry import Inquiry
from app.models.portal_view import PortalDailyView
from app.models.seller_inquiry import SellerInquiry
from app.models.user import User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
PORTALS = ("buyer", "seller", "admin")


class ViewEvent(BaseModel):
    portal: str


@router.post("/view", status_code=204)
async def record_view(
    data: ViewEvent,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if data.portal not in PORTALS:
        raise HTTPException(status_code=422, detail="Unknown portal")
    if request.headers.get("origin", "").rstrip("/") not in get_cors_origins():
        raise HTTPException(status_code=403, detail="Web origin required")
    if data.portal == "admin" and (not user or user.role != "admin" or user.restricted_port not in (None, "admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    if data.portal == "seller" and (not user or user.role not in ("seller", "admin") or user.restricted_port not in (None, "seller")):
        raise HTTPException(status_code=403, detail="Seller access required")
    if rate_exceeded(f"view:{get_client_ip(request)}", 120):
        raise HTTPException(status_code=429, detail="Too many view events")

    statement = insert(PortalDailyView).values(day=datetime.now(timezone.utc).date(), portal=data.portal, views=1)
    statement = statement.on_conflict_do_update(
        index_elements=[PortalDailyView.day, PortalDailyView.portal],
        set_={"views": PortalDailyView.views + 1},
    )
    await db.execute(statement)
    await db.commit()
    return Response(status_code=204)


@router.get("/admin")
async def admin_trends(
    response: Response,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    response.headers["Cache-Control"] = "no-store"
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    since = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    rows = {start + timedelta(days=i): {
        "date": (start + timedelta(days=i)).isoformat(),
        "buyer_views": 0, "seller_views": 0, "admin_views": 0,
        "analyses": 0, "sent_inquiries": 0,
        "new_buyers": 0, "new_sellers": 0,
    } for i in range(days)}

    views = await db.execute(select(PortalDailyView.day, PortalDailyView.portal, PortalDailyView.views)
                             .where(PortalDailyView.day >= start))
    for day, portal, count in views:
        if day in rows and portal in PORTALS:
            rows[day][f"{portal}_views"] = count

    async def counts_by_day(model, *extra_filters):
        utc_day = cast(func.timezone("UTC", model.created_at), Date)
        result = await db.execute(select(utc_day, func.count(model.id))
                                  .where(model.created_at >= since, *extra_filters)
                                  .group_by(utc_day))
        return result.all()

    for day, count in await counts_by_day(Inquiry):
        if day in rows:
            rows[day]["analyses"] = count
    for day, count in await counts_by_day(SellerInquiry):
        if day in rows:
            rows[day]["sent_inquiries"] = count

    utc_day = cast(func.timezone("UTC", User.created_at), Date)
    registrations = await db.execute(select(utc_day, User.role, func.count(User.id))
                                     .where(User.created_at >= since, User.role.in_(("buyer", "seller")))
                                     .group_by(utc_day, User.role))
    for day, role, count in registrations:
        if day in rows:
            rows[day][f"new_{role}s"] = count

    return {"timezone": "UTC", "days": list(rows.values())}
