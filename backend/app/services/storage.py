"""
Storage abstraction layer.

Local development (and the current Railway deployment) default to LocalStorage.
R2Storage can be enabled by setting STORAGE_BACKEND=r2 together with the R2_*
settings. Business code only talks to the StorageService interface and never
depends on the concrete backend.
"""
import asyncio
import os
import uuid

from app.core.config import settings


def _safe_filename(filename: str) -> str:
    name = (filename or "").replace("\\", "/").split("/")[-1]
    return name.strip() or "upload"


def _generate_key(filename: str) -> str:
    return f"{uuid.uuid4().hex[:12]}_{_safe_filename(filename)}"


class StorageService:
    async def save(self, filename: str, content: bytes) -> str:
        raise NotImplementedError

    async def read(self, key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalStorage(StorageService):
    """Writes files to a local directory (default: <backend>/uploads)."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    async def save(self, filename: str, content: bytes) -> str:
        key = _generate_key(filename)
        path = os.path.join(self.base_dir, key)
        with open(path, "wb") as f:
            f.write(content)
        return path

    async def read(self, key: str) -> bytes:
        with open(key, "rb") as f:
            return f.read()

    async def delete(self, key: str) -> None:
        try:
            os.remove(key)
        except FileNotFoundError:
            pass

    async def exists(self, key: str) -> bool:
        return os.path.isfile(key)


class R2Storage(StorageService):
    """Stores objects in a Cloudflare R2 bucket via its S3-compatible API."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        account_id: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        endpoint_url: str = "",
    ):
        self.bucket = bucket
        self.prefix = (prefix or "").strip("/")
        self._account_id = account_id
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._endpoint_url = endpoint_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise RuntimeError(
                    "R2Storage requires the 'boto3' package. Install it with `pip install boto3`."
                ) from e

            endpoint = self._endpoint_url or (
                f"https://{self._account_id}.r2.cloudflarestorage.com"
                if self._account_id
                else ""
            )
            kwargs = {
                "endpoint_url": endpoint or None,
                "aws_access_key_id": self._access_key_id or None,
                "aws_secret_access_key": self._secret_access_key or None,
                "region_name": "auto",
            }
            self._client = boto3.client(
                "s3", **{k: v for k, v in kwargs.items() if v is not None}
            )
        return self._client

    def _object_key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    async def save(self, filename: str, content: bytes) -> str:
        key = _generate_key(filename)
        obj_key = self._object_key(key)
        client = await asyncio.to_thread(self._get_client)
        await asyncio.to_thread(
            client.put_object, Bucket=self.bucket, Key=obj_key, Body=content
        )
        return obj_key

    async def read(self, key: str) -> bytes:
        client = await asyncio.to_thread(self._get_client)
        obj = await asyncio.to_thread(
            client.get_object, Bucket=self.bucket, Key=key
        )
        return obj["Body"].read()

    async def delete(self, key: str) -> None:
        client = await asyncio.to_thread(self._get_client)
        await asyncio.to_thread(
            client.delete_object, Bucket=self.bucket, Key=key
        )

    async def exists(self, key: str) -> bool:
        client = await asyncio.to_thread(self._get_client)
        try:
            await asyncio.to_thread(client.head_object, Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            response = getattr(e, "response", None) or {}
            error = response.get("Error", {}) if isinstance(response, dict) else {}
            if error.get("Code") in ("404", "NoSuchKey"):
                return False
            raise


_storage: StorageService | None = None


def _resolve_local_dir() -> str:
    if settings.STORAGE_LOCAL_DIR:
        return settings.STORAGE_LOCAL_DIR
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "uploads",
    )


def _build_storage() -> StorageService:
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if backend == "r2":
        return R2Storage(
            bucket=settings.R2_BUCKET,
            prefix=settings.R2_STORAGE_PREFIX,
            account_id=settings.R2_ACCOUNT_ID,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            endpoint_url=settings.R2_ENDPOINT_URL,
        )
    return LocalStorage(base_dir=_resolve_local_dir())


def get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = _build_storage()
    return _storage
