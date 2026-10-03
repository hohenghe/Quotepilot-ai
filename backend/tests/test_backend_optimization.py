"""Offline checks for concurrency guards and bounded backend work."""

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.dialects import postgresql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import http_clients
from app.core import ratelimit
from app.models.product import Product
from app.services import embedding, file_parser, rag
from app.services import llm
from app.core.retry import embedding_api_call_with_retry
from app.services.rating import compute_seller_scores


class FakeSession:
    def __init__(self, product, write_rowcount):
        self.statements = []
        self.results = iter([
            SimpleNamespace(all=lambda: [(product, False)]),
            SimpleNamespace(rowcount=1),
            SimpleNamespace(rowcount=write_rowcount),
        ])
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def execute(self, statement):
        self.statements.append(statement)
        return next(self.results)


def test_embedding_claim_and_write_are_guarded():
    product = Product(id=7, name="Lamp", category="lighting", is_active=True)
    db = FakeSession(product, write_rowcount=0)  # concurrent edit moved it to pending

    async def run():
        with patch.object(embedding, "async_session", return_value=db), \
             patch.object(embedding, "is_embedding_available", return_value=True), \
             patch.object(embedding, "embedding_api_call_with_retry", new=AsyncMock(return_value=[[1.0, 2.0]])), \
             patch.object(embedding.settings, "EMBEDDING_DIM", 2):
            return await embedding.process_pending_embeddings()

    result = asyncio.run(run())
    claim_sql = str(db.statements[0].compile(dialect=postgresql.dialect()))
    write_sql = str(db.statements[2].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in claim_sql
    assert "products.embedding," not in claim_sql.split("FROM")[0]
    assert "products.embedding_status =" in write_sql
    assert "products.is_active = true" in write_sql
    assert result["processed"] == 0
    assert db.commit.await_count == 3


def test_keyword_fallback_ranks_before_limit():
    from app.services.rag import _keyword_order

    statement = (rag.select(Product)
                 .where(Product.is_active == True)
                 .order_by(_keyword_order("LED lamp").desc())
                 .limit(100))
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY least(" in sql
    assert sql.index("ORDER BY") < sql.index("LIMIT")
    assert len(rag._keywords(" ".join(f"word{i}" for i in range(50)))) == 32


def test_parser_keeps_event_loop_responsive():
    original = file_parser._parse_csv

    def slow_parse(content):
        time.sleep(0.05)
        return original(content)

    async def run():
        heartbeat = asyncio.Event()

        async def tick():
            await asyncio.sleep(0.005)
            heartbeat.set()

        with patch.object(file_parser, "_parse_csv", side_effect=slow_parse):
            task = asyncio.create_task(file_parser.parse_file(
                "products.csv", b"name,sku\nLamp,L1\n"
            ))
            await tick()
            assert heartbeat.is_set() and not task.done()
            return await task

    assert asyncio.run(run())[0]["sku"] == "L1"


def test_scores_are_batched_and_match_existing_formula():
    rows = [(1, 5.0, "great", []), (1, 3.0, "", ["img"]), (2, 4.0, None, [])]
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))
    result = asyncio.run(compute_seller_scores(db, [1, 2, 3]))
    assert result == {1: 3.7, 2: 4.0}
    assert db.execute.await_count == 1


def test_http_pool_is_reused_and_closed():
    async def run():
        first = http_clients.get_http_client()
        assert http_clients.get_http_client() is first
        await http_clients.close_http_client()
        assert first.is_closed

    asyncio.run(run())


def test_text_and_embedding_calls_share_the_pool():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"embedding": [1.0, 2.0]}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(http_clients, "_client", client), \
             patch.object(llm.settings, "OPENAI_BASE_URL", "https://mock/v1"), \
             patch.object(llm.settings, "EMBEDDING_BASE_URL", "https://mock/v1"):
            assert await llm._call_llm("system", "user") == "ok"
            assert await embedding_api_call_with_retry(["lamp"], max_retries=0) == [[1.0, 2.0]]
            await client.aclose()

    asyncio.run(run())
    assert paths == ["/v1/chat/completions", "/v1/embeddings"]


def test_rate_limit_state_stays_bounded_for_new_clients():
    with patch.object(ratelimit, "_MAX_WINDOW_KEYS", 3), \
         patch.object(ratelimit.time, "monotonic", return_value=100.0):
        ratelimit._windows.clear()
        ratelimit._last_sweep = 0.0
        for key in ("a", "b", "c", "d"):
            assert not ratelimit.rate_exceeded(key, 2)
        assert len(ratelimit._windows) == 3
        assert "a" not in ratelimit._windows
        assert ratelimit.rate_exceeded("d", 1)
    ratelimit._windows.clear()
