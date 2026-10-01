"""Regression tests for pgvector dimension detection without a database."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.core import database


def _connection_with_dimension(dimension):
    conn = Mock()
    conn.execute = AsyncMock(side_effect=[
        Mock(first=Mock(return_value=("USER-DEFINED", "vector"))),
        Mock(first=Mock(return_value=(dimension,))),
        Mock(),
        Mock(),
        Mock(),
    ])
    return conn


def test_matching_pgvector_dimension_preserves_embeddings():
    conn = _connection_with_dimension(1024)
    with patch.object(database.settings, "EMBEDDING_DIM", 1024):
        asyncio.run(database._migrate_embedding_dimension(conn))

    assert conn.execute.await_count == 2
    executed_sql = [str(call.args[0]) for call in conn.execute.await_args_list]
    assert not any("DROP COLUMN" in sql or "UPDATE products" in sql for sql in executed_sql)


def test_genuine_pgvector_dimension_change_requeues_products():
    conn = _connection_with_dimension(768)
    with patch.object(database.settings, "EMBEDDING_DIM", 1024):
        asyncio.run(database._migrate_embedding_dimension(conn))

    executed_sql = [str(call.args[0]) for call in conn.execute.await_args_list]
    assert "ALTER TABLE products DROP COLUMN embedding" in executed_sql
    assert "ALTER TABLE products ADD COLUMN embedding vector(1024)" in executed_sql
    assert any("UPDATE products SET embedding_status='pending'" in sql for sql in executed_sql)
