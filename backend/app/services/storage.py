"""One lazy R2 client for product documents and uploaded media."""

import asyncio
import re
import threading
import uuid
from urllib.parse import urlsplit

from botocore.exceptions import ClientError

from app.core.config import settings


MEDIA_KIND_PREFIX = {
    "review": "reviews", "product": "products",
    "avatar": "avatars", "license": "licenses",
}
_MEDIA_NAME = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.(?:jpg|png|webp|gif)$")
_DOCUMENT_MIME = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv",
}


class R2ConfigurationError(RuntimeError):
    """A required R2 setting is missing or invalid."""


def validate_r2_config() -> None:
    """Validate locally at startup or use; never contact R2 during import."""
    required = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    missing = [name for name in required if not getattr(settings, name).strip()]
    if missing:
        raise R2ConfigurationError("Missing R2 configuration: " + ", ".join(missing))
    endpoint = urlsplit(settings.R2_ENDPOINT)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in ("", "/"):
        raise R2ConfigurationError("R2_ENDPOINT must be an HTTPS S3 API endpoint")
    if not settings.R2_REGION.strip():
        raise R2ConfigurationError("R2_REGION must not be empty")


def media_key(kind: str, extension: str) -> str:
    if kind not in MEDIA_KIND_PREFIX:
        raise ValueError("Unsupported upload kind")
    if extension not in {".jpg", ".png", ".webp", ".gif"}:
        raise ValueError("Unsupported image type")
    return f"{MEDIA_KIND_PREFIX[kind]}/{uuid.uuid4()}{extension}"


def is_media_key(key: str, kind: str) -> bool:
    prefix = MEDIA_KIND_PREFIX.get(kind)
    return bool(prefix and key.startswith(prefix + "/") and _MEDIA_NAME.fullmatch(key[len(prefix) + 1:]))


def document_key(filename: str) -> str:
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in _DOCUMENT_MIME:
        raise ValueError("Unsupported document type")
    return f"documents/{uuid.uuid4()}{extension}"


class R2Storage:
    """S3 compatible storage; boto3 work runs outside the event loop."""

    def __init__(self):
        self._client = None
        self._client_lock = threading.Lock()

    def _get_client(self):
        validate_r2_config()
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    import boto3
                    self._client = boto3.client(
                        "s3", endpoint_url=settings.R2_ENDPOINT,
                        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                        region_name=settings.R2_REGION,
                    )
        return self._client

    async def upload(self, key: str, content: bytes, content_type: str) -> str:
        client = await asyncio.to_thread(self._get_client)
        await asyncio.to_thread(
            client.put_object, Bucket=settings.R2_BUCKET, Key=key,
            Body=content, ContentType=content_type,
        )
        return key

    async def save(self, filename: str, content: bytes) -> str:
        key = document_key(filename)
        extension = "." + filename.rsplit(".", 1)[-1].lower()
        return await self.upload(key, content, _DOCUMENT_MIME[extension])

    async def read(self, key: str) -> bytes:
        client = await asyncio.to_thread(self._get_client)

        def fetch():
            response = client.get_object(Bucket=settings.R2_BUCKET, Key=key)
            with response["Body"] as body:
                return body.read()

        return await asyncio.to_thread(fetch)

    async def delete(self, key: str) -> None:
        client = await asyncio.to_thread(self._get_client)
        await asyncio.to_thread(client.delete_object, Bucket=settings.R2_BUCKET, Key=key)

    async def exists(self, key: str) -> bool:
        client = await asyncio.to_thread(self._get_client)
        try:
            await asyncio.to_thread(client.head_object, Bucket=settings.R2_BUCKET, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    async def generate_presigned_get_url(self, key: str, expires_in: int = 3600) -> str:
        client = await asyncio.to_thread(self._get_client)
        return await asyncio.to_thread(
            client.generate_presigned_url, "get_object",
            Params={"Bucket": settings.R2_BUCKET, "Key": key}, ExpiresIn=expires_in,
        )


_storage = R2Storage()


def get_storage() -> R2Storage:
    return _storage


def validate_media_reference(value: str | None, kind: str, *, base_url: str, existing: str | None = None) -> str | None:
    """Accept a backend object URL or an unchanged legacy value."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Image URL cannot be empty")
    if value == existing:
        return value
    prefix = f"{base_url.rstrip('/')}/api/files/objects/{kind}/"
    if not value.startswith(prefix):
        raise ValueError("Image must be uploaded through /api/files/upload")
    name = value[len(prefix):]
    if not is_media_key(f"{MEDIA_KIND_PREFIX[kind]}/{name}", kind):
        raise ValueError("Invalid image reference")
    return value


def validate_media_references(values: list[str], kind: str, *, base_url: str, existing: list[str] | None = None) -> list[str]:
    old = set(existing or [])
    return [validate_media_reference(value, kind, base_url=base_url, existing=value if value in old else None) for value in values]
