"""Offline SQL/response regression checks; never connect to production."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.api.products import list_products
from app.models.product import Product
from app.services.embedding import _recheck_product
from app.services import rag


class QueryFootprintTests(unittest.IsolatedAsyncioTestCase):
    async def test_product_list_excludes_vector_and_preserves_payload(self):
        product = Product(id=1, name="LED lamp", category="lighting", is_active=True, images=[], view_count=0)
        db = SimpleNamespace(execute=AsyncMock(side_effect=[SimpleNamespace(scalar=lambda: 1), SimpleNamespace(all=lambda: [(product, 3)])]))
        response = await list_products(page=1, page_size=20, category=None, search=None, db=db, user=SimpleNamespace(id=7))
        sql = str(db.execute.call_args_list[1].args[0])
        selected = sql.split("FROM")[0]
        self.assertNotIn("products.embedding,", selected)
        self.assertIn("products.seller_id =", sql)
        self.assertEqual(response.items[0].name, "LED lamp")
        self.assertEqual(response.items[0].favorite_count, 3)
        self.assertEqual(response.total, 1)

    async def test_active_recheck_only_loads_id(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 1)))
        self.assertEqual(await _recheck_product(db, 1), 1)
        sql = str(db.execute.call_args.args[0])
        self.assertEqual(sql.split("FROM")[0].strip(), "SELECT products.id")
        self.assertIn("products.is_active", sql)

    async def test_keyword_fallback_keeps_matching_without_vector(self):
        product = Product(id=1, name="LED lamp", category="lighting", seller_id=7, is_active=True)
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [product]))))
        with patch.object(rag, "is_embedding_available", return_value=False):
            result = await rag.search_products_hybrid(db, "LED lamp")
        self.assertNotIn("products.embedding,", str(db.execute.call_args.args[0]).split("FROM")[0])
        self.assertEqual(result[0]["product_id"], 1)


if __name__ == "__main__":
    unittest.main()
