"""Admin embedding diagnostics: real-call contract without network or database."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import admin
from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app


class AdminEmbeddingConsoleTests(unittest.IsolatedAsyncioTestCase):
    def test_input_limits(self):
        for value in ("", "   ", "x" * 501):
            with self.assertRaises(ValidationError):
                admin.TestEmbeddingRequest(text_a=value, text_b="valid")
        data = admin.TestEmbeddingRequest(text_a="  lamp  ", text_b=" light ")
        self.assertEqual((data.text_a, data.text_b), ("lamp", "light"))

    async def test_live_call_returns_diagnostics_without_vectors(self):
        vectors = [[1.0] + [0.0] * 1023, [0.6, 0.8] + [0.0] * 1022]
        call = AsyncMock(return_value=vectors)
        with patch.object(admin, "is_embedding_available", return_value=True), patch.object(
            admin, "embedding_api_call_with_retry", call
        ):
            result = await admin.test_embedding(
                admin.TestEmbeddingRequest(text_a="lamp", text_b="light"), SimpleNamespace(id=1)
            )
        call.assert_awaited_once_with(["lamp", "light"], max_retries=0)
        self.assertEqual(result["dimension"], 1024)
        self.assertEqual(result["similarity"], 0.6)
        self.assertNotIn("vectors", result)
        self.assertNotIn("lamp", str(result))

    async def test_missing_config_and_invalid_provider_vectors_fail(self):
        data = admin.TestEmbeddingRequest(text_a="lamp", text_b="light")
        with patch.object(admin, "is_embedding_available", return_value=False):
            with self.assertRaises(HTTPException) as error:
                await admin.test_embedding(data, SimpleNamespace(id=1))
            self.assertEqual(error.exception.status_code, 503)

        for vectors in ([[], []], [[1.0], [1.0]],
                        [[float("nan")] + [0.0] * 1023, [1.0] + [0.0] * 1023]):
            with patch.object(admin, "is_embedding_available", return_value=True), patch.object(
                admin, "embedding_api_call_with_retry", AsyncMock(return_value=vectors)
            ):
                with self.assertRaises(HTTPException) as error:
                    await admin.test_embedding(data, SimpleNamespace(id=1))
                self.assertEqual(error.exception.status_code, 502)

    async def test_route_rejects_anonymous_and_buyer_before_model_call(self):
        async def unused_db():
            yield SimpleNamespace()

        app.dependency_overrides[get_db] = unused_db
        call = AsyncMock()
        try:
            with patch.object(admin, "embedding_api_call_with_retry", call):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    payload = {"text_a": "lamp", "text_b": "light"}
                    anonymous = await client.post("/api/admin/tests/embedding", json=payload)
                    self.assertEqual(anonymous.status_code, 401)
                    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                        id=2, role="buyer", restricted_port="buyer"
                    )
                    buyer = await client.post("/api/admin/tests/embedding", json=payload)
                    self.assertEqual(buyer.status_code, 403)
            call.assert_not_awaited()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    async def test_admin_recognition_uses_product_flow_without_writing_data(self):
        async def unused_db():
            yield SimpleNamespace()

        app.dependency_overrides[get_db] = unused_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=3, role="admin", restricted_port="admin"
        )
        recognition = AsyncMock(return_value={"success": True, "data": {"name": "Lamp"}})
        try:
            with patch.object(admin, "product_recognize", recognition):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    status = await client.get("/api/admin/tests/recognition/status")
                    self.assertEqual(status.status_code, 200)
                    self.assertEqual(set(status.json()), {"configured", "ocr_model", "vision_model"})
                    result = await client.post("/api/admin/tests/recognition", files={
                        "file": ("lamp.jpg", b"\xff\xd8\xfftest", "image/jpeg")
                    })
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json()["data"]["name"], "Lamp")
                    self.assertEqual(recognition.await_args.args[1].id, 3)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)


if __name__ == "__main__":
    unittest.main()
