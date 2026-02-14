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
                json={"data": _make_base64_image()},
            )
            assert response.status_code == 200
            data = response.json()
            assert "image_id" in data
            assert "url" in data
            assert "/images/test-ns/" in data["url"]

    async def test_upload_invalid_namespace(self, client: AsyncClient) -> None:
        response = await client.post(
            "/images/..secret",
            json={"data": _make_base64_image()},
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
    async def test_fetch_success(self, client: AsyncClient) -> None:
        test_image = _make_test_image()
        with patch(
            "src.services.image_fetcher.fetch_image",
            new_callable=AsyncMock,
            return_value=test_image,
        ):
            response = await client.post(
                "/images/fetch",
                json={"url": "https://example.com/image.jpg"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "mime_type" in data
            assert data["mime_type"] == "image/jpeg"

    async def test_fetch_failure(self, client: AsyncClient) -> None:
        with patch(
            "src.services.image_fetcher.fetch_image",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.post(
                "/images/fetch",
                json={"url": "https://example.com/broken.jpg"},
            )
            assert response.status_code == 502

    async def test_fetch_with_pool(self, client: AsyncClient) -> None:
        test_image = _make_test_image()
        mock_fetch = AsyncMock(return_value=test_image)
        with patch("src.services.image_fetcher.fetch_image", mock_fetch):
            response = await client.post(
                "/images/fetch",
                json={"url": "https://example.com/image.jpg", "pool": "foreign"},
            )
            assert response.status_code == 200
            mock_fetch.assert_called_once_with("https://example.com/image.jpg", pool="foreign")


class TestFetchUrlValidation:
    async def test_rejects_ftp_scheme(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "ftp://example.com/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_javascript_scheme(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "javascript:alert(1)"})
        assert response.status_code == 400

    async def test_rejects_localhost(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://localhost/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_localhost_subdomain(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://evil.localhost/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_private_ip(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://192.168.1.1/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_loopback_ip(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://127.0.0.1/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_link_local_ip(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://169.254.0.1/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_no_hostname(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http:///no-host"})
        assert response.status_code == 400

    async def test_allows_public_ip(self, client: AsyncClient) -> None:
        test_image = _make_test_image()
        with patch("src.services.image_fetcher.fetch_image", new_callable=AsyncMock, return_value=test_image):
            response = await client.post("/images/fetch", json={"url": "http://8.8.8.8/img.jpg"})
            assert response.status_code == 200

    async def test_rejects_10_network(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://10.0.0.1/img.jpg"})
        assert response.status_code == 400

    async def test_rejects_multicast_ip(self, client: AsyncClient) -> None:
        response = await client.post("/images/fetch", json={"url": "http://224.0.0.1/img.jpg"})
        assert response.status_code == 400


class TestProxyImages:
    async def test_proxy_success(self, client: AsyncClient, tmp_path: Path) -> None:
        test_image = _make_test_image()
        with (
            patch("src.services.image_fetcher.fetch_image", new_callable=AsyncMock, return_value=test_image),
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
        ):
            response = await client.post(
                "/images/test-ns/proxy",
                json={"urls": ["https://example.com/a.jpg", "https://example.com/b.jpg"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["urls"]) == 2

    async def test_proxy_partial_failure(self, client: AsyncClient, tmp_path: Path) -> None:
        test_image = _make_test_image()

        async def _side_effect(url: str, pool: str | None = None) -> bytes | None:
            if "fail" in url:
                return None
            return test_image

        with (
            patch("src.services.image_fetcher.fetch_image", new_callable=AsyncMock, side_effect=_side_effect),
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
        ):
            response = await client.post(
                "/images/test-ns/proxy",
                json={"urls": ["https://example.com/ok.jpg", "https://example.com/fail.jpg"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["urls"]) == 1

    async def test_proxy_invalid_namespace(self, client: AsyncClient) -> None:
        response = await client.post("/images/..evil/proxy", json={"urls": []})
        assert response.status_code == 400

    async def test_proxy_with_pool(self, client: AsyncClient, tmp_path: Path) -> None:
        test_image = _make_test_image()
        mock_fetch = AsyncMock(return_value=test_image)
        with (
            patch("src.services.image_fetcher.fetch_image", mock_fetch),
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
        ):
            response = await client.post(
                "/images/test-ns/proxy",
                json={"urls": ["https://example.com/a.jpg"], "pool": "mypool"},
            )
            assert response.status_code == 200
            mock_fetch.assert_called_once_with("https://example.com/a.jpg", pool="mypool")

    async def test_proxy_skips_blocked_urls(self, client: AsyncClient, tmp_path: Path) -> None:
        test_image = _make_test_image()
        with (
            patch("src.services.image_fetcher.fetch_image", new_callable=AsyncMock, return_value=test_image),
            patch.object(image_hosting, "IMAGES_DIR", tmp_path),
        ):
            response = await client.post(
                "/images/test-ns/proxy",
                json={"urls": ["http://192.168.1.1/img.jpg", "https://example.com/ok.jpg"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["urls"]) <= 1

    async def test_proxy_empty_urls(self, client: AsyncClient) -> None:
        response = await client.post("/images/test-ns/proxy", json={"urls": []})
        assert response.status_code == 200
        assert response.json()["urls"] == {}


class TestUploadImageExtended:
    async def test_upload_with_data_url_prefix(self, client: AsyncClient, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            b64 = f"data:image/jpeg;base64,{_make_base64_image()}"
            response = await client.post("/images/test-ns", json={"data": b64})
            assert response.status_code == 200
            assert "image_id" in response.json()

    async def test_upload_empty_namespace(self, client: AsyncClient) -> None:
        response = await client.post("/images/", json={"data": _make_base64_image()})
        assert response.status_code in (400, 404, 405)

    async def test_upload_save_failure(self, client: AsyncClient) -> None:
        with patch.object(image_hosting, "save_image", return_value=None):
            response = await client.post("/images/test-ns", json={"data": "invalid-b64"})
            assert response.status_code == 500

    async def test_upload_missing_data(self, client: AsyncClient) -> None:
        response = await client.post("/images/test-ns", json={})
        assert response.status_code == 422


class TestDeleteImagesExtended:
    async def test_delete_invalid_namespace(self, client: AsyncClient) -> None:
        response = await client.delete("/images/..evil")
        assert response.status_code == 400

    async def test_delete_slash_namespace(self, client: AsyncClient) -> None:
        response = await client.delete("/images/a/b")
        assert response.status_code in (400, 404, 405)
