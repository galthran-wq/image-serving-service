from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services import image_fetcher


class TestLoadProxiesFromFile:
    def test_loads_proxies(self, tmp_path: Path) -> None:
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://proxy1:8080\nhttp://proxy2:8080\n\n  \n")
        result = image_fetcher._load_proxies_from_file(str(proxy_file))
        assert result == ["http://proxy1:8080", "http://proxy2:8080"]

    def test_empty_file(self, tmp_path: Path) -> None:
        proxy_file = tmp_path / "empty.txt"
        proxy_file.write_text("\n  \n")
        result = image_fetcher._load_proxies_from_file(str(proxy_file))
        assert result == []

    def test_missing_file(self) -> None:
        result = image_fetcher._load_proxies_from_file("/nonexistent/path.txt")
        assert result == []


class TestBuildProxyPools:
    def test_from_settings_proxies(self) -> None:
        with (
            patch.object(image_fetcher.settings, "proxies", {"pool1": ["http://p1", "http://p2"]}),
            patch.object(image_fetcher.settings, "proxy_files", {}),
        ):
            result = image_fetcher._build_proxy_pools()
            assert result == {"pool1": ["http://p1", "http://p2"]}

    def test_from_proxy_files(self, tmp_path: Path) -> None:
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://file-proxy:8080\n")
        with (
            patch.object(image_fetcher.settings, "proxies", {}),
            patch.object(image_fetcher.settings, "proxy_files", {"pool2": str(proxy_file)}),
        ):
            result = image_fetcher._build_proxy_pools()
            assert result == {"pool2": ["http://file-proxy:8080"]}

    def test_merged_pools(self, tmp_path: Path) -> None:
        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://file-proxy:8080\n")
        with (
            patch.object(image_fetcher.settings, "proxies", {"shared": ["http://p1"]}),
            patch.object(image_fetcher.settings, "proxy_files", {"shared": str(proxy_file)}),
        ):
            result = image_fetcher._build_proxy_pools()
            assert result == {"shared": ["http://p1", "http://file-proxy:8080"]}

    def test_empty_pools_excluded(self) -> None:
        with (
            patch.object(image_fetcher.settings, "proxies", {"empty": []}),
            patch.object(image_fetcher.settings, "proxy_files", {}),
        ):
            result = image_fetcher._build_proxy_pools()
            assert result == {}


class TestFetchImage:
    async def test_fetch_success(self) -> None:
        fake_data = b"\xff\xd8fake-image-bytes"
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}
        mock_response.aiter_bytes = lambda: _async_iter([fake_data])

        mock_client = MagicMock()
        mock_client.stream = _make_async_context_manager(mock_response)

        with patch.object(image_fetcher, "get_http_client", return_value=mock_client):
            result = await image_fetcher.fetch_image("https://example.com/img.jpg")
            assert result == fake_data

    async def test_fetch_returns_none_on_exception(self) -> None:
        mock_client = MagicMock()
        mock_client.stream = MagicMock(side_effect=Exception("connection error"))

        with patch.object(image_fetcher, "get_http_client", return_value=mock_client):
            result = await image_fetcher.fetch_image("https://example.com/bad.jpg")
            assert result is None

    async def test_fetch_respects_content_length_limit(self) -> None:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"Content-Length": str(999_999_999)}
        mock_response.aiter_bytes = lambda: _async_iter([b"x"])

        mock_client = MagicMock()
        mock_client.stream = _make_async_context_manager(mock_response)

        with patch.object(image_fetcher, "get_http_client", return_value=mock_client):
            result = await image_fetcher.fetch_image("https://example.com/huge.jpg")
            assert result is None

    async def test_fetch_with_pool(self) -> None:
        fake_data = b"\xff\xd8data"
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {}
        mock_response.aiter_bytes = lambda: _async_iter([fake_data])

        mock_client = MagicMock()
        mock_client.stream = _make_async_context_manager(mock_response)

        with patch.object(image_fetcher, "get_http_client", return_value=mock_client):
            result = await image_fetcher.fetch_image("https://example.com/img.jpg", pool="mypool")
            assert result == fake_data
            mock_client.stream.assert_called_once_with("GET", "https://example.com/img.jpg", pool="mypool")


class TestCloseClient:
    async def test_close_when_client_exists(self) -> None:
        mock_client = AsyncMock()
        original = image_fetcher._client
        try:
            image_fetcher._client = mock_client
            await image_fetcher.close_client()
            mock_client.aclose.assert_called_once()
            assert image_fetcher._client is None
        finally:
            image_fetcher._client = original

    async def test_close_when_no_client(self) -> None:
        original = image_fetcher._client
        try:
            image_fetcher._client = None
            await image_fetcher.close_client()
            assert image_fetcher._client is None
        finally:
            image_fetcher._client = original


class TestGetHttpClient:
    def test_creates_client_lazily(self) -> None:
        original = image_fetcher._client
        try:
            image_fetcher._client = None
            with (
                patch.object(image_fetcher.settings, "proxies", {}),
                patch.object(image_fetcher.settings, "proxy_files", {}),
            ):
                client = image_fetcher.get_http_client()
                assert client is not None
                assert image_fetcher._client is client
        finally:
            image_fetcher._client = original

    def test_returns_same_client(self) -> None:
        original = image_fetcher._client
        try:
            image_fetcher._client = None
            with (
                patch.object(image_fetcher.settings, "proxies", {}),
                patch.object(image_fetcher.settings, "proxy_files", {}),
            ):
                c1 = image_fetcher.get_http_client()
                c2 = image_fetcher.get_http_client()
                assert c1 is c2
        finally:
            image_fetcher._client = original


async def _async_iter(items: list[bytes]):  # type: ignore[no-untyped-def]
    for item in items:
        yield item


def _make_async_context_manager(return_value: object) -> MagicMock:
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock = MagicMock(return_value=cm)
    return mock
