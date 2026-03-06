import base64
import secrets
import uuid
from io import BytesIO

import structlog
from PIL import Image

from src.config import settings
from src.services.storage import get_storage

logger = structlog.get_logger()

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


async def _save_bytes(namespace: str, image_bytes: bytes, max_size: int) -> str | None:
    try:
        resized_bytes, img_format = _resize_image(image_bytes, max_size)
        ext = FORMAT_TO_EXT.get(img_format, "jpg")
        image_id = generate_image_id()
        storage = get_storage()
        await storage.save(namespace, image_id, resized_bytes, ext)
        return image_id
    except Exception as e:
        logger.error("image_save_failed", namespace=namespace, error=str(e))
        return None


async def save_image(namespace: str, base64_data: str) -> str | None:
    try:
        if ";base64," in base64_data:
            base64_data = base64_data.split(";base64,")[1]
        image_bytes = base64.b64decode(base64_data)
        return await _save_bytes(namespace, image_bytes, settings.max_upload_size)
    except Exception as e:
        logger.error("image_save_failed", namespace=namespace, error=str(e))
        return None


async def save_image_bytes(namespace: str, image_bytes: bytes) -> str | None:
    return await _save_bytes(namespace, image_bytes, settings.max_fetch_size)


async def get_image(namespace: str, image_id: str) -> tuple[bytes, str] | None:
    storage = get_storage()
    return await storage.get(namespace, image_id)


async def get_image_url(namespace: str, image_id: str, base_url: str) -> str:
    storage = get_storage()
    return await storage.url(namespace, image_id, base_url)


async def delete_namespace_images(namespace: str) -> int:
    storage = get_storage()
    return await storage.delete_namespace(namespace)
