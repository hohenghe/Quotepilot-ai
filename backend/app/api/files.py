import logging
import os
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.core.auth import require_auth
from app.models.user import User
from app.services.storage import upload_file as upload_to_r2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# Legacy local-disk images (served only for backward compatibility).
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGES_DIR = os.path.join(_BASE_DIR, "uploads", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
SAFE_NAME = re.compile(r"^[0-9a-f]{32}\.(png|jpg|jpeg|gif|webp)$")
MAX_SIZE = 5 * 1024 * 1024

# Magic-byte signatures for real content validation (never trust Content-Type alone).
_IMAGE_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # RIFF....WEBP
}


def _verify_image_magic(content: bytes, content_type: str) -> bool:
    sigs = _IMAGE_MAGIC.get(content_type)
    if sigs is None:
        return False
    return content.startswith(sigs)

# Object-key prefix per upload kind (client cannot control the key).
KIND_PREFIX = {
    "review": "reviews",
    "product": "products",
    "avatar": "avatars",
    "license": "licenses",
}


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    kind: str = Form("review"),
    _: User = Depends(require_auth),
):
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    content_type = (file.content_type or "").lower()
    ext = os.path.splitext(file.filename or "")[1].lower()

    if content_type in ALLOWED_MIME:
        ext = MIME_TO_EXT[content_type]
    elif ext in ALLOWED_EXT:
        content_type = EXT_TO_MIME[ext]
    else:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    # Validate actual content against magic bytes (don't trust the Content-Type header).
    if not _verify_image_magic(content, content_type):
        raise HTTPException(status_code=400, detail="File content does not match the declared image type")

    prefix = KIND_PREFIX.get(kind)
    if prefix is None:
        raise HTTPException(status_code=400, detail="Unsupported upload kind")

    object_key = f"{prefix}/{uuid.uuid4()}{ext}"
    try:
        url = await upload_to_r2(object_key, content, content_type)
    except Exception as e:
        logger.error("R2 upload failed: %s", type(e).__name__)
        raise HTTPException(status_code=502, detail="File upload failed")

    return {"url": url}


@router.get("/images/{name}")
async def get_image(name: str):
    # Legacy compatibility: serves previously uploaded local files only.
    if not SAFE_NAME.match(name):
        raise HTTPException(status_code=404, detail="Not found")
    path = os.path.join(IMAGES_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    ext = os.path.splitext(name)[1].lower()
    return FileResponse(path, media_type=EXT_TO_MIME.get(ext, "application/octet-stream"))
