import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from PIL import Image
from src.services import image_hosting


def _make_test_image(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def _make_base64_image(width: int = 100, height: int = 100) -> str:
    return base64.b64encode(_make_test_image(width, height)).decode()


class TestUploadImage:
    async def test_upload_success(self, client: AsyncClient, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            response = await client.post(
                "/images/test-ns",
                json={"data": _make_base64_image(), "mime_type": "image/jpeg"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "image_id" in data
            assert "url" in data
            assert "/images/test-ns/" in data["url"]

    async def test_upload_invalid_namespace(self, client: AsyncClient) -> None:
        response = await client.post(
            "/images/..secret",
            json={"data": _make_base64_image(), "mime_type": "image/jpeg"},
        )
        assert response.status_code == 400


class TestGetImage:
    async def test_get_existing_image(self, client: AsyncClient, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            b64 = _make_base64_image()
            image_id = image_hosting.save_image("test-ns", b64)
            assert image_id is not None

            response = await client.get(f"/images/test-ns/{image_id}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert "cache-control" in response.headers

    async def test_get_nonexistent_image(self, client: AsyncClient, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            response = await client.get("/images/test-ns/nonexistent")
            assert response.status_code == 404

    async def test_get_invalid_path(self, client: AsyncClient) -> None:
        response = await client.get("/images/test-ns/..evil-id")
        assert response.status_code == 400


class TestDeleteImages:
    async def test_delete_namespace(self, client: AsyncClient, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            image_hosting.save_image("del-ns", _make_base64_image())
            image_hosting.save_image("del-ns", _make_base64_image())

            response = await client.delete("/images/del-ns")
            assert response.status_code == 200
            assert response.json()["deleted_count"] == 2

    async def test_delete_empty_namespace(self, client: AsyncClient, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            response = await client.delete("/images/empty-ns")
            assert response.status_code == 200
            assert response.json()["deleted_count"] == 0


class TestFetchExternalImage:
    async def test_fetch_success(self, client: AsyncClient, tmp_path: Path) -> None:
        test_image = _make_test_image()
        with (
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
            patch(
                "src.services.image_fetcher.fetch_image",
                new_callable=AsyncMock,
                return_value=test_image,
            ),
        ):
            response = await client.post(
                "/images/test-ns/fetch",
                json={"url": "https://example.com/image.jpg"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "image_id" in data
            assert "url" in data

    async def test_fetch_failure(self, client: AsyncClient, tmp_path: Path) -> None:
        with (
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
            patch(
                "src.services.image_fetcher.fetch_image",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await client.post(
                "/images/test-ns/fetch",
                json={"url": "https://example.com/broken.jpg"},
            )
            assert response.status_code == 502

    async def test_fetch_with_pool(self, client: AsyncClient, tmp_path: Path) -> None:
        test_image = _make_test_image()
        mock_fetch = AsyncMock(return_value=test_image)
        with (
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
            patch("src.services.image_fetcher.fetch_image", mock_fetch),
        ):
            response = await client.post(
                "/images/test-ns/fetch",
                json={"url": "https://example.com/image.jpg", "pool": "foreign"},
            )
            assert response.status_code == 200
            mock_fetch.assert_called_once_with("https://example.com/image.jpg", pool="foreign")
