import os
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from app.core.auth import require_auth
from app.models.user import User

router = APIRouter(prefix="/api/files", tags=["files"])

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGES_DIR = os.path.join(_BASE_DIR, "uploads", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
SAFE_NAME = re.compile(r"^[0-9a-f]{32}\.(png|jpg|jpeg|gif|webp)$")


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    _: User = Depends(require_auth),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(IMAGES_DIR, name)
    with open(path, "wb") as f:
        f.write(content)

    return {"url": f"/api/files/images/{name}"}


@router.get("/images/{name}")
async def get_image(name: str):
    if not SAFE_NAME.match(name):
        raise HTTPException(status_code=404, detail="Not found")
    path = os.path.join(IMAGES_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    ext = os.path.splitext(name)[1].lower()
    return FileResponse(path, media_type=CONTENT_TYPES.get(ext, "application/octet-stream"))
