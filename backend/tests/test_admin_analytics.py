"""Web view attribution and bounded admin analytics responses."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException, Response
from sqlalchemy.dialects import postgresql

from app.api import analytics


class AnalyticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = SimpleNamespace(headers={"origin": "http://localhost:3000"},
                                       client=SimpleNamespace(host="127.0.0.1"))
        self.db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
        self.admin = SimpleNamespace(role="admin", restricted_port=None)

    async def test_admin_view_requires_admin_and_records_one_daily_increment(self):
        with self.assertRaises(HTTPException) as denied:
            await analytics.record_view(analytics.ViewEvent(portal="admin"), self.request, self.db, None)
        self.assertEqual(denied.exception.status_code, 403)
        self.db.execute.assert_not_awaited()

        with patch.object(analytics, "rate_exceeded", return_value=False):
            response = await analytics.record_view(analytics.ViewEvent(portal="admin"),
                                                   self.request, self.db, self.admin)
        self.assertEqual(response.status_code, 204)
        statement = self.db.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("ON CONFLICT", sql)
        self.db.commit.assert_awaited_once()

    async def test_view_rejects_cross_origin_and_rate_limited_requests(self):
        foreign = SimpleNamespace(headers={"origin": "https://evil.example"},
                                  client=SimpleNamespace(host="127.0.0.1"))
        with self.assertRaises(HTTPException) as denied:
            await analytics.record_view(analytics.ViewEvent(portal="buyer"), foreign, self.db, None)
        self.assertEqual(denied.exception.status_code, 403)
        with patch.object(analytics, "rate_exceeded", return_value=True):
            with self.assertRaises(HTTPException) as limited:
                await analytics.record_view(analytics.ViewEvent(portal="buyer"), self.request, self.db, None)
        self.assertEqual(limited.exception.status_code, 429)
        self.db.execute.assert_not_awaited()

    async def test_trends_fill_missing_days_and_keep_portals_separate(self):
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        results = [
            [(today, "buyer", 4), (today, "admin", 2)],
            [(today, 3)],
            [(yesterday, 1)],
            [(today, "seller", 2)],
        ]
        class QueryRows:
            def __init__(self, rows):
                self.rows = rows

            def __iter__(self):
                return iter(self.rows)

            def all(self):
                return self.rows

        self.db.execute.side_effect = [QueryRows(rows) for rows in results]
        response = Response()
        data = await analytics.admin_trends(response, 7, self.db, self.admin)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(len(data["days"]), 7)
        self.assertEqual(data["days"][-1]["buyer_views"], 4)
        self.assertEqual(data["days"][-1]["admin_views"], 2)
        self.assertEqual(data["days"][-1]["analyses"], 3)
        self.assertEqual(data["days"][-1]["new_sellers"], 2)
        self.assertEqual(data["days"][-2]["sent_inquiries"], 1)
        self.assertEqual(data["days"][0]["buyer_views"], 0)
