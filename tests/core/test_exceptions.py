from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from src.core.exceptions import AppError
from src.main import app


class _DummyBody(BaseModel):
    value: int


@app.post("/_validate")
async def _validation_endpoint(body: _DummyBody) -> _DummyBody:
    return body


async def test_validation_error_format() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/_validate", json={"value": "not_an_int"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)
    error = data["detail"][0]
    assert "loc" in error
    assert "msg" in error
    assert "type" in error
    assert "url" not in error


async def test_validation_error_missing_field() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/_validate", json={})
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)
    assert any("value" in str(e["loc"]) for e in data["detail"])


class TestAppError:
    def test_stores_status_and_detail(self) -> None:
        err = AppError(status_code=404, detail="Not found")
        assert err.status_code == 404
        assert err.detail == "Not found"

    async def test_app_error_handler_returns_json(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/nonexistent-ns/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert data == {"detail": "Image not found"}

    async def test_app_error_400(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/test-ns/..evil")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
