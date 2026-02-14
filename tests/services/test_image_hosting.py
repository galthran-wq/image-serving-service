import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from src.services import image_hosting


def _make_test_image(width: int = 100, height: int = 100, fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()


def _make_base64_image(width: int = 100, height: int = 100) -> str:
    return base64.b64encode(_make_test_image(width, height)).decode()


class TestDetectImageFormat:
    def test_jpeg(self) -> None:
        data = _make_test_image(fmt="JPEG")
        assert image_hosting._detect_image_format(data) == "jpeg"

    def test_png(self) -> None:
        data = _make_test_image(fmt="PNG")
        assert image_hosting._detect_image_format(data) == "png"

    def test_gif(self) -> None:
        data = _make_test_image(fmt="GIF")
        assert image_hosting._detect_image_format(data) == "gif"

    def test_webp(self) -> None:
        data = _make_test_image(fmt="WEBP")
        assert image_hosting._detect_image_format(data) == "webp"

    def test_unknown_defaults_to_jpeg(self) -> None:
        assert image_hosting._detect_image_format(b"\x00\x00\x00") == "jpeg"


class TestResizeImage:
    def test_no_resize_when_within_limit(self) -> None:
        data = _make_test_image(50, 50)
        resized, fmt = image_hosting._resize_image(data, 100)
        assert fmt == "jpeg"
        img = Image.open(BytesIO(resized))
        assert img.size[0] <= 100
        assert img.size[1] <= 100

    def test_resize_when_exceeds_limit(self) -> None:
        data = _make_test_image(2000, 1000)
        resized, fmt = image_hosting._resize_image(data, 800)
        assert fmt == "jpeg"
        img = Image.open(BytesIO(resized))
        assert img.size[0] <= 800
        assert img.size[1] <= 800


class TestSaveAndGetImage:
    def test_save_and_retrieve(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            b64 = _make_base64_image()
            image_id = image_hosting.save_image("test-ns", b64)
            assert image_id is not None

            result = image_hosting.get_image_path("test-ns", image_id)
            assert result is not None
            path, media_type = result
            assert path.exists()
            assert media_type == "image/jpeg"

    def test_save_with_data_url_prefix(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            b64 = f"data:image/jpeg;base64,{_make_base64_image()}"
            image_id = image_hosting.save_image("test-ns", b64)
            assert image_id is not None

    def test_get_nonexistent_returns_none(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            assert image_hosting.get_image_path("no-ns", "no-id") is None


class TestSaveImageBytes:
    def test_save_bytes(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            data = _make_test_image()
            image_id = image_hosting.save_image_bytes("test-ns", data)
            assert image_id is not None

            result = image_hosting.get_image_path("test-ns", image_id)
            assert result is not None


class TestDeleteNamespaceImages:
    def test_delete(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            b64 = _make_base64_image()
            image_hosting.save_image("del-ns", b64)
            image_hosting.save_image("del-ns", b64)

            count = image_hosting.delete_namespace_images("del-ns")
            assert count == 2
            assert not (tmp_path / "del-ns").exists()

    def test_delete_nonexistent_returns_zero(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            assert image_hosting.delete_namespace_images("nope") == 0


class TestGetImageUrl:
    def test_url_format(self) -> None:
        url = image_hosting.get_image_url("ns1", "img1", "http://localhost:8000")
        assert url == "http://localhost:8000/images/ns1/img1"

    def test_strips_trailing_slash(self) -> None:
        url = image_hosting.get_image_url("ns1", "img1", "http://localhost:8000/")
        assert url == "http://localhost:8000/images/ns1/img1"
