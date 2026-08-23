import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.auth import require_seller
from app.models.user import User
from app.services.vision import recognize_product_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["ai"])

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB

# Magic-byte signatures for real content validation.
_IMAGE_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}

# Simple in-memory per-user rate limit (no persistence; enough for the single
# worker deployment).
RATE_LIMIT = 10
RATE_WINDOW_SECONDS = 60
_rate_log: dict[int, deque] = defaultdict(deque)


class RecognizedFields(BaseModel):
    name: str | None = None
    sku: str | None = None
    category: str | None = None
    description: str | None = None
    technical_specs: str | None = None
    certifications: str | None = None
    moq: int | None = None
    unit_price: float | None = None
    price_range_low: float | None = None
    price_range_high: float | None = None
    pricing: str | None = None
    lead_time_days: int | None = None


class ProductRecognitionResponse(BaseModel):
    success: bool
    data: RecognizedFields


def _rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    dq = _rate_log[user_id]
    while dq and now - dq[0] > RATE_WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return True
    dq.append(now)
    return False


@router.post("/recognize", response_model=ProductRecognitionResponse)
async def product_recognize(
    file: UploadFile = File(...),
    user: User = Depends(require_seller),
):
    if _rate_limited(user.id):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Unsupported image type (use jpg, jpeg, png, or webp)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Image too large (max 5MB)")

    # Validate actual content against magic bytes (don't trust the Content-Type header).
    sigs = _IMAGE_MAGIC.get(content_type)
    if not sigs or not content.startswith(sigs):
        raise HTTPException(status_code=400, detail="File content does not match the declared image type")

    try:
        fields = await recognize_product_image(content, content_type)
    except Exception as e:
        logger.warning("product recognition failed (%s)", type(e).__name__)
        raise HTTPException(status_code=502, detail="AI recognition service unavailable")

    return ProductRecognitionResponse(success=True, data=RecognizedFields(**fields))
