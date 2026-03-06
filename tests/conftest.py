from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app
from src.services import storage as storage_module


@pytest.fixture(autouse=True)
def _reset_storage() -> None:
    storage_module._storage = None
    yield  # type: ignore[misc]
    storage_module._storage = None


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
