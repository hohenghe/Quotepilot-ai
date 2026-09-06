"""Unit tests for transient database startup retry behavior (no real DB)."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app import main


def test_database_init_retries_then_succeeds():
    async def run():
        init = AsyncMock(side_effect=[OSError("Connection refused"), None])
        sleep = AsyncMock()
        with patch.object(main, "init_db", init), patch.object(main.asyncio, "sleep", sleep):
            await main.initialize_database_with_retry()
        assert init.await_count == 2
        sleep.assert_awaited_once_with(1)

    asyncio.run(run())


def test_database_init_raises_after_eight_connection_failures():
    async def run():
        init = AsyncMock(side_effect=OSError("Connection refused"))
        sleep = AsyncMock()
        with patch.object(main, "init_db", init), patch.object(main.asyncio, "sleep", sleep):
            with pytest.raises(OSError, match="Connection refused"):
                await main.initialize_database_with_retry()
        assert init.await_count == 8
        assert [call.args[0] for call in sleep.await_args_list] == [1, 2, 4, 8, 15, 15, 15]

    asyncio.run(run())


def test_database_init_does_not_retry_non_connection_error():
    async def run():
        init = AsyncMock(side_effect=OperationalError("SELECT", {}, Exception("syntax error")))
        sleep = AsyncMock()
        with patch.object(main, "init_db", init), patch.object(main.asyncio, "sleep", sleep):
            with pytest.raises(OperationalError, match="syntax error"):
                await main.initialize_database_with_retry()
        init.assert_awaited_once()
        sleep.assert_not_awaited()

    asyncio.run(run())
