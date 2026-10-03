from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.review import Review


def review_weight(review: Review) -> float:
    """Weight of a review when computing the seller's score.

    Reviews with more words and with attached images carry higher weight:
      - base weight: 1.0
      - content length: up to +2.0 (saturates at 100 characters)
      - images: +1.0 (flat bonus for having at least one image)
    """
    return _review_weight_values(review.content, review.images)


def _review_weight_values(content: str | None, images: list | None) -> float:
    weight = 1.0
    content = (content or "").strip()
    if content:
        weight += min(len(content) / 50.0, 2.0)
    if images:
        weight += 1.0
    return weight


async def compute_seller_score(db: AsyncSession, seller_id: int) -> float | None:
    """Weighted average of the seller's review ratings.

    Returns None when the seller has no reviews.
    """
    reviews = (await db.execute(
        select(Review).where(Review.seller_id == seller_id)
    )).scalars().all()

    if not reviews:
        return None

    weighted_sum = 0.0
    total_weight = 0.0
    for review in reviews:
        w = review_weight(review)
        weighted_sum += (review.rating or 0.0) * w
        total_weight += w

    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 1)


async def compute_seller_scores(db: AsyncSession, seller_ids: list[int]) -> dict[int, float]:
    """Score a page of sellers with one review query instead of one per seller."""
    if not seller_ids:
        return {}
    rows = (await db.execute(
        select(Review.seller_id, Review.rating, Review.content, Review.images)
        .where(Review.seller_id.in_(seller_ids))
    )).all()
    totals: dict[int, list[float]] = {}
    for seller_id, rating, content, images in rows:
        weight = _review_weight_values(content, images)
        weighted_sum, total_weight = totals.setdefault(seller_id, [0.0, 0.0])
        totals[seller_id] = [weighted_sum + (rating or 0.0) * weight, total_weight + weight]
    return {
        seller_id: round(weighted_sum / total_weight, 1)
        for seller_id, (weighted_sum, total_weight) in totals.items()
        if total_weight
    }
