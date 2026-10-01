"""Regression checks for the index that keeps vector inquiry matching scalable.

These tests inspect the migration SQL rather than requiring a PostgreSQL server.
"""
from pathlib import Path
import unittest


DATABASE_MODULE = (
    Path(__file__).resolve().parents[1] / "app" / "core" / "database.py"
)


class VectorIndexDefinitionTests(unittest.TestCase):
    def test_completed_product_cosine_hnsw_index_is_migrated(self):
        source = DATABASE_MODULE.read_text(encoding="utf-8")
        self.assertIn("ix_products_embedding_hnsw_cosine", source)
        self.assertIn("USING hnsw (embedding vector_cosine_ops)", source)
        self.assertIn(
            "WHERE is_active = true AND embedding_status = 'completed'", source
        )


if __name__ == "__main__":
    unittest.main()
