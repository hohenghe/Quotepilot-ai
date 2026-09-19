"""Offline regression tests for customization supplier matching."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.supplier_matching import select_supplier_matches
from app.schemas.inquiry import InquiryCreate
from app.api import inquiries


class SupplierMatchingTests(unittest.TestCase):
    def test_normal_search_stays_default(self):
        self.assertFalse(InquiryCreate(raw_message='LED lights').custom_products)
        self.assertTrue(InquiryCreate(raw_message='LED lights', custom_products=True).custom_products)

    def test_best_product_per_supplier_and_ranking(self):
        matches = [
            dict(product_id=1, seller_id=10, match_score=0.2),
            dict(product_id=2, seller_id=20, match_score=0.8),
            dict(product_id=3, seller_id=10, match_score=0.9),
        ]
        selected = select_supplier_matches(matches, {10: 'A', 20: 'B'})
        self.assertEqual([item['product_id'] for item in selected], [3, 2])
        self.assertEqual(len(matches), 3)

    def test_missing_disabled_or_unrelated_suppliers_are_excluded(self):
        matches = [dict(product_id=i, seller_id=seller, match_score=score)
                   for i, seller, score in [(1, None, 1), (2, 99, 1), (3, 10, 0), (4, 20, 0.5)]]
        selected = select_supplier_matches(matches, {10: 'A', 20: 'B'})
        self.assertEqual([item['product_id'] for item in selected], [4])
        self.assertEqual(select_supplier_matches([], {}), [])

    def test_duplicate_products_do_not_consume_supplier_slots(self):
        matches = [dict(product_id=i, seller_id=10, match_score=1) for i in range(20)]
        matches += [dict(product_id=100+i, seller_id=i, match_score=0.8) for i in range(1, 8)]
        selected = select_supplier_matches(matches, {i: str(i) for i in range(1, 11)})
        self.assertEqual(len(selected), 5)
        self.assertEqual(len({item['seller_id'] for item in selected}), 5)


class SupplierEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_custom_and_regular_search_response(self):
        matches = [dict(product_id=i, product_name='LED', seller_id=seller, match_score=score)
                   for i, seller, score in [(1, 10, 0.9), (2, 10, 0.8), (3, 20, 0.7)]]
        analysis = dict(product_category='electronics', quantity=None, technical_params={}, target_price=None,
                        required_certifications=[], delivery_location=None, delivery_country=None, missing_info=[])
        for custom in (False, True):
            def add(row):
                row.id = 1
            db = SimpleNamespace(add=add, flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock(),
                execute=AsyncMock(side_effect=[SimpleNamespace(all=lambda: []),
                    SimpleNamespace(all=lambda: [(10, 'A', None, None), (20, 'B', None, None)]), None]))
            with patch.object(inquiries, 'rate_exceeded', return_value=False), \
                 patch.object(inquiries, 'get_client_ip', return_value='test'), \
                 patch.object(inquiries, 'analyze_inquiry', AsyncMock(return_value=analysis)), \
                 patch.object(inquiries, 'search_products_hybrid', AsyncMock(return_value=matches)) as search:
                result = await inquiries.analyze_and_match(InquiryCreate(raw_message='LED', custom_products=custom), None, db, None)
            self.assertEqual(search.call_args.kwargs['top_k'], 50 if custom else 5)
            self.assertEqual([m.seller_id for m in result.matched_products], [10, 20] if custom else [10, 10, 20])
            db.commit.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
