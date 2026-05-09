from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set; skipping checkpointer integration tests")
    return url


@pytest_asyncio.fixture
async def saver(database_url: str):
    async with AsyncConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=2,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    ) as pool:
        await pool.open()
        s = AsyncPostgresSaver(pool)
        await s.setup()
        yield s


@pytest.fixture
def thread_id() -> str:
    return f"pytest-{uuid.uuid4()}"
