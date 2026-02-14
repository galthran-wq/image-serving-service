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


class TestDetectMimeType:
    def test_jpeg_mime(self) -> None:
        data = _make_test_image(fmt="JPEG")
        assert image_hosting.detect_mime_type(data) == "image/jpeg"

    def test_png_mime(self) -> None:
        data = _make_test_image(fmt="PNG")
        assert image_hosting.detect_mime_type(data) == "image/png"

    def test_gif_mime(self) -> None:
        data = _make_test_image(fmt="GIF")
        assert image_hosting.detect_mime_type(data) == "image/gif"

    def test_webp_mime(self) -> None:
        data = _make_test_image(fmt="WEBP")
        assert image_hosting.detect_mime_type(data) == "image/webp"

    def test_unknown_defaults_to_jpeg(self) -> None:
        assert image_hosting.detect_mime_type(b"\x00\x00\x00") == "image/jpeg"


class TestSaveImageBytes:
    def test_save_bytes_success(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            image_bytes = _make_test_image()
            image_id = image_hosting.save_image_bytes("test-ns", image_bytes)
            assert image_id is not None
            result = image_hosting.get_image_path("test-ns", image_id)
            assert result is not None

    def test_save_bytes_invalid_data(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            result = image_hosting.save_image_bytes("test-ns", b"not-an-image")
            assert result is None


class TestGenerateImageId:
    def test_uniqueness(self) -> None:
        ids = {image_hosting.generate_image_id() for _ in range(100)}
        assert len(ids) == 100

    def test_format(self) -> None:
        image_id = image_hosting.generate_image_id()
        assert "-" in image_id
        assert len(image_id) > 20


class TestResizeImageExtended:
    def test_landscape_resize_ratio(self) -> None:
        data = _make_test_image(2000, 1000)
        resized, _ = image_hosting._resize_image(data, 800)
        img = Image.open(BytesIO(resized))
        assert img.size[0] == 800
        assert img.size[1] == 400

    def test_portrait_resize_ratio(self) -> None:
        data = _make_test_image(500, 2000)
        resized, _ = image_hosting._resize_image(data, 800)
        img = Image.open(BytesIO(resized))
        assert img.size[1] == 800
        assert img.size[0] == 200

    def test_rgba_converted_to_rgb(self) -> None:
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        resized, fmt = image_hosting._resize_image(buffer.getvalue(), 200)
        assert fmt == "jpeg"
        result_img = Image.open(BytesIO(resized))
        assert result_img.mode == "RGB"

    def test_palette_mode_converted(self) -> None:
        img = Image.new("P", (100, 100))
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        resized, fmt = image_hosting._resize_image(buffer.getvalue(), 200)
        assert fmt == "jpeg"
        result_img = Image.open(BytesIO(resized))
        assert result_img.mode == "RGB"


class TestSaveImageInvalid:
    def test_invalid_base64(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            result = image_hosting.save_image("test-ns", "!!!not-base64!!!")
            assert result is None

    def test_valid_base64_but_not_image(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            data = base64.b64encode(b"just some text").decode()
            result = image_hosting.save_image("test-ns", data)
            assert result is None


class TestEnsureNamespaceDir:
    def test_creates_nested_dir(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            ns_dir = image_hosting._ensure_namespace_dir("new-ns")
            assert ns_dir.exists()
            assert ns_dir == tmp_path / "new-ns"

    def test_idempotent(self, tmp_path: Path) -> None:
        with patch.object(image_hosting, "IMAGES_DIR", tmp_path):
            d1 = image_hosting._ensure_namespace_dir("ns")
            d2 = image_hosting._ensure_namespace_dir("ns")
            assert d1 == d2
