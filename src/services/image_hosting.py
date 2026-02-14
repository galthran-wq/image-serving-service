import base64
import contextlib
import secrets
import uuid
from io import BytesIO
from pathlib import Path

import structlog
from PIL import Image

from src.config import settings

logger = structlog.get_logger()

IMAGES_DIR = Path(settings.uploads_path) / "images"

FORMAT_TO_EXT = {
    "jpeg": "jpg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
}

FORMAT_TO_MEDIA_TYPE = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def detect_mime_type(image_bytes: bytes) -> str:
    fmt = _detect_image_format(image_bytes)
    return FORMAT_TO_MEDIA_TYPE.get(fmt, "image/jpeg")


def _detect_image_format(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "jpeg"


def _ensure_namespace_dir(namespace: str) -> Path:
    namespace_dir = IMAGES_DIR / namespace
    namespace_dir.mkdir(parents=True, exist_ok=True)
    return namespace_dir


def _resize_image(image_bytes: bytes, max_size: int) -> tuple[bytes, str]:
    img: Image.Image = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    width, height = img.size
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue(), "jpeg"


def generate_image_id() -> str:
    return f"{uuid.uuid4().hex}-{secrets.token_urlsafe(8)}"


def save_image(namespace: str, base64_data: str) -> str | None:
    try:
        if ";base64," in base64_data:
            base64_data = base64_data.split(";base64,")[1]

        image_bytes = base64.b64decode(base64_data)
        resized_bytes, img_format = _resize_image(image_bytes, settings.max_upload_size)

        ext = FORMAT_TO_EXT.get(img_format, "jpg")
        namespace_dir = _ensure_namespace_dir(namespace)
        image_id = generate_image_id()
        image_path = namespace_dir / f"{image_id}.{ext}"

        with open(image_path, "wb") as f:
            f.write(resized_bytes)

        logger.info("image_saved", namespace=namespace, image_id=image_id)
        return image_id
    except Exception as e:
        logger.error("image_save_failed", namespace=namespace, error=str(e))
        return None


def get_image_path(namespace: str, image_id: str) -> tuple[Path, str] | None:
    namespace_dir = IMAGES_DIR / namespace
    for ext in ["jpg", "png", "gif", "webp"]:
        image_path = namespace_dir / f"{image_id}.{ext}"
        if image_path.exists():
            return image_path, FORMAT_TO_MEDIA_TYPE.get(ext, "image/jpeg")
    return None


def get_image_url(namespace: str, image_id: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/images/{namespace}/{image_id}"


def delete_namespace_images(namespace: str) -> int:
    namespace_dir = IMAGES_DIR / namespace
    if not namespace_dir.exists():
        return 0

    count = 0
    for ext in ["jpg", "png", "gif", "webp"]:
        for image_file in namespace_dir.glob(f"*.{ext}"):
            try:
                image_file.unlink()
                count += 1
            except Exception as e:
                logger.error("image_delete_failed", path=str(image_file), error=str(e))

    with contextlib.suppress(Exception):
        namespace_dir.rmdir()

    logger.info("namespace_images_deleted", namespace=namespace, count=count)
    return count
