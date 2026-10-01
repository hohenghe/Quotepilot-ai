"""R2 storage and media API contract tests; no database or network access."""

import asyncio
import io
import os
import sys
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

import botocore.session
from fastapi import HTTPException, Request, UploadFile
from botocore.exceptions import ClientError

from app.api.files import get_r2_media, upload_image
from app.api.media import require_media_url, require_media_urls
from app import main as main_module
from app.core.config import Settings, settings
from app.main import app
from app.services import storage


def request():
    return Request({
        "type": "http", "http_version": "1.1", "method": "POST",
        "scheme": "https", "path": "/api/files/upload", "root_path": "",
        "query_string": b"", "headers": [(b"host", b"api.example.test")],
        "server": ("api.example.test", 443), "client": ("127.0.0.1", 1234),
        "app": app,
    })


class R2MediaTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        for name, value in {
            "R2_ENDPOINT": "https://example.r2.cloudflarestorage.com",
            "R2_ACCESS_KEY_ID": "test-key",
            "R2_SECRET_ACCESS_KEY": "test-secret",
            "R2_BUCKET": "test-bucket",
            "R2_REGION": "auto",
        }.items():
            self.stack.enter_context(patch.object(settings, name, value))
        self.client = Mock()
        self.service = storage.R2Storage()
        self.service._client = self.client
        self.stack.enter_context(patch("app.api.files.get_storage", return_value=self.service))

    def tearDown(self):
        self.stack.close()

    def test_upload_kinds_and_redirect(self):
        for kind, prefix in storage.MEDIA_KIND_PREFIX.items():
            with self.subTest(kind=kind):
                file = UploadFile(
                    filename="untrusted.png", file=io.BytesIO(b"\x89PNG\r\n\x1a\ncontent"),
                    headers={"content-type": "image/png"},
                )
                result = asyncio.run(upload_image(request=request(), file=file, kind=kind, _=None))
                self.assertTrue(result["url"].startswith(f"https://api.example.test/api/files/objects/{kind}/"))
                kwargs = self.client.put_object.call_args.kwargs
                self.assertEqual(kwargs["Bucket"], "test-bucket")
                self.assertTrue(storage.is_media_key(kwargs["Key"], kind))
                self.assertEqual(kwargs["ContentType"], "image/png")
                self.assertEqual(require_media_url(result["url"], kind, request=request()), result["url"])
                name = kwargs["Key"].split("/", 1)[1]
                self.client.generate_presigned_url.return_value = "https://signed.example.test/object?signature=secret"
                response = asyncio.run(get_r2_media(kind, name))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["cache-control"], "private, no-store")
                self.client.generate_presigned_url.assert_called_with(
                    "get_object", Params={"Bucket": "test-bucket", "Key": kwargs["Key"]}, ExpiresIn=3600,
                )

    def test_document_key_and_content_type(self):
        key = asyncio.run(self.service.save("../invoice.pdf", b"%PDF-1.7"))
        self.assertTrue(key.startswith("documents/"))
        self.assertNotIn("invoice", key)
        self.assertEqual(self.client.put_object.call_args.kwargs["ContentType"], "application/pdf")
        self.assertEqual(self.client.put_object.call_args.kwargs["Key"], key)

    def test_client_uses_only_configured_r2_endpoint_and_credentials(self):
        service = storage.R2Storage()
        factory = Mock(return_value=self.client)
        with patch.dict(sys.modules, {"boto3": SimpleNamespace(client=factory)}):
            self.assertIs(service._get_client(), self.client)
            self.assertIs(service._get_client(), self.client)
        factory.assert_called_once_with(
            "s3", endpoint_url="https://example.r2.cloudflarestorage.com",
            aws_access_key_id="test-key", aws_secret_access_key="test-secret",
            region_name="auto",
        )

    def test_missing_config_rejected_before_write(self):
        with patch.object(settings, "R2_SECRET_ACCESS_KEY", ""):
            with self.assertRaises(storage.R2ConfigurationError) as context:
                asyncio.run(self.service.upload("documents/test.pdf", b"x", "application/pdf"))
            self.assertIn("R2_SECRET_ACCESS_KEY", str(context.exception))
            self.client.put_object.assert_not_called()

    def test_settings_load_fixed_r2_names(self):
        with patch.dict(os.environ, {
            "R2_ENDPOINT": "https://example.r2.cloudflarestorage.com",
            "R2_ACCESS_KEY_ID": "test-key",
            "R2_SECRET_ACCESS_KEY": "test-secret",
            "R2_BUCKET": "test-bucket",
            "R2_REGION": "auto",
        }, clear=True):
            configured = Settings(_env_file=None)
        self.assertEqual(configured.R2_ENDPOINT, "https://example.r2.cloudflarestorage.com")
        self.assertEqual(configured.R2_BUCKET, "test-bucket")
        self.assertEqual(configured.R2_REGION, "auto")

    def test_production_startup_checks_r2_before_database(self):
        async def start():
            async with main_module.lifespan(app):
                pass

        with patch.object(settings, "R2_ENDPOINT", ""), \
             patch.object(main_module, "is_production", return_value=True), \
             patch.object(main_module, "initialize_database_with_retry", new_callable=AsyncMock) as database:
            with self.assertRaises(storage.R2ConfigurationError):
                asyncio.run(start())
            database.assert_not_awaited()

    def test_missing_and_delete(self):
        error = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        self.client.head_object.side_effect = error
        self.assertFalse(asyncio.run(self.service.exists("documents/missing.pdf")))
        asyncio.run(self.service.delete("documents/missing.pdf"))
        self.client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="documents/missing.pdf")

    def test_real_sigv4_get_url_has_one_hour_expiry(self):
        self.service._client = botocore.session.get_session().create_client(
            "s3", endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name=settings.R2_REGION,
        )
        signed = asyncio.run(self.service.generate_presigned_get_url("products/example.png"))
        parsed = urlsplit(signed)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.hostname, "example.r2.cloudflarestorage.com")
        self.assertEqual(query["X-Amz-Expires"], ["3600"])
        self.assertIn("X-Amz-Signature", query)

    def test_references_and_legacy(self):
        valid = "https://api.example.test/api/files/objects/avatar/00000000-0000-4000-8000-000000000001.png"
        self.assertEqual(require_media_url(valid, "avatar", request=request()), valid)
        for bad in (
            valid.replace("api.example.test", "other.example.test"),
            valid.replace("/avatar/", "/product/"),
            valid + "?redirect=1",
            "/api/files/images/old.png",
        ):
            with self.subTest(value=bad), self.assertRaises(HTTPException):
                require_media_url(bad, "avatar", request=request())
        legacy = "/api/files/images/old.png"
        self.assertEqual(require_media_urls([legacy], "review", request=request(), existing=[legacy]), [legacy])

    def test_invalid_media_route(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(get_r2_media("product", "../../bad.png"))
        self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
