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
    weight = 1.0
    content = (review.content or "").strip()
    if content:
        weight += min(len(content) / 50.0, 2.0)
    if review.images:
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
