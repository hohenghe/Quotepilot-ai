"""Seller mini-program home summary without a database or network."""

import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import Response
import httpx
from sqlalchemy.dialects import postgresql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.dashboard import seller_home
from app.main import app
from app.core.auth import require_seller
from app.core.database import get_db


class SellerHomeTests(unittest.TestCase):
    def test_small_home_payload_and_query_scope(self):
        counts = Mock()
        counts.one.return_value = (7, 12, 4, 6)
        recent = Mock()
        recent.all.return_value = [SimpleNamespace(
            id=101, buyer_email="buyer@example.test", status="pending",
            raw_message="Need a quote",
        )]
        reviews = Mock()
        reviews.all.return_value = [(42, 4.5, "Great", [])]
        db = SimpleNamespace(execute=AsyncMock(side_effect=[counts, recent, reviews]))
        user = SimpleNamespace(
            id=42, email="seller@example.test", store_name="Store",
            name="Seller", uid="S42",
        )

        response = Response()
        payload = asyncio.run(seller_home(response=response, db=db, user=user))

        self.assertEqual(db.execute.await_count, 3)
        self.assertEqual(payload["product_count"], 7)
        self.assertEqual(payload["inquiry_count"], 12)
        self.assertEqual(payload["pending_count"], 4)
        self.assertEqual(payload["replied_count"], 6)
        self.assertEqual(payload["score"], 4.5)
        self.assertEqual(payload["inquiries"], [{
            "id": 101, "buyer_email": "buyer@example.test",
            "status": "pending", "raw_message": "Need a quote",
        }])
        self.assertNotIn("reply_body", str(payload))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("counts;dur=", response.headers["Server-Timing"])

        count_sql = str(db.execute.await_args_list[0].args[0].compile(dialect=postgresql.dialect()))
        recent_sql = str(db.execute.await_args_list[1].args[0].compile(dialect=postgresql.dialect()))
        self.assertIn("products.seller_id", count_sql)
        self.assertIn("products.is_active", count_sql)
        self.assertIn("seller_inquiries.seller_id", count_sql)
        self.assertIn("seller_inquiries.seller_id", recent_sql)
        self.assertIn("LIMIT", recent_sql)

    def test_empty_seller_has_zero_counts_and_no_score(self):
        counts = Mock()
        counts.one.return_value = (0, 0, 0, 0)
        empty = Mock()
        empty.all.return_value = []
        db = SimpleNamespace(execute=AsyncMock(side_effect=[counts, empty, empty]))
        user = SimpleNamespace(id=1, email=None, store_name=None, name=None, uid=None)

        payload = asyncio.run(seller_home(response=Response(), db=db, user=user))

        self.assertEqual(payload["product_count"], 0)
        self.assertEqual(payload["inquiry_count"], 0)
        self.assertEqual(payload["inquiries"], [])
        self.assertIsNone(payload["score"])

    def test_route_rejects_unauthenticated_requests(self):
        async def run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/api/dashboard/seller-home")

        response = asyncio.run(run())
        self.assertEqual(response.status_code, 401)

    def test_asgi_route_returns_private_summary(self):
        counts = Mock()
        counts.one.return_value = (2, 3, 1, 2)
        empty = Mock()
        empty.all.return_value = []
        db = SimpleNamespace(execute=AsyncMock(side_effect=[counts, empty, empty]))
        user = SimpleNamespace(id=5, email=None, store_name="Test", name=None, uid="U5")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_seller] = lambda: user
        try:
            async def run():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    return await client.get("/api/dashboard/seller-home")

            response = asyncio.run(run())
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(require_seller, None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product_count"], 2)
        self.assertEqual(response.json()["store_name"], "Test")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("score;dur=", response.headers["Server-Timing"])


if __name__ == "__main__":
    unittest.main()
