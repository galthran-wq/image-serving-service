import asyncio
import contextlib
from pathlib import Path

import structlog

from src.services.image_hosting import FORMAT_TO_MEDIA_TYPE

logger = structlog.get_logger()


class LocalStorageBackend:
    def __init__(self, uploads_path: str) -> None:
        self._images_dir = Path(uploads_path) / "images"

    def _namespace_dir(self, namespace: str) -> Path:
        return self._images_dir / namespace

    async def save(self, namespace: str, image_id: str, data: bytes, ext: str) -> None:
        namespace_dir = self._namespace_dir(namespace)

        def _write() -> None:
            namespace_dir.mkdir(parents=True, exist_ok=True)
            path = namespace_dir / f"{image_id}.{ext}"
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        logger.info("image_saved", namespace=namespace, image_id=image_id)

    async def get(self, namespace: str, image_id: str) -> tuple[bytes, str] | None:
        namespace_dir = self._namespace_dir(namespace)

        def _read() -> tuple[bytes, str] | None:
            for ext in ("jpg", "png", "gif", "webp"):
                path = namespace_dir / f"{image_id}.{ext}"
                if path.exists():
                    return path.read_bytes(), FORMAT_TO_MEDIA_TYPE.get(ext, "image/jpeg")
            return None

        return await asyncio.to_thread(_read)

    async def delete_namespace(self, namespace: str) -> int:
        namespace_dir = self._namespace_dir(namespace)

        def _delete() -> int:
            if not namespace_dir.exists():
                return 0
            count = 0
            for ext in ("jpg", "png", "gif", "webp"):
                for image_file in namespace_dir.glob(f"*.{ext}"):
                    try:
                        image_file.unlink()
                        count += 1
                    except Exception as e:
                        logger.error("image_delete_failed", path=str(image_file), error=str(e))
            with contextlib.suppress(Exception):
                namespace_dir.rmdir()
            return count

        count = await asyncio.to_thread(_delete)
        logger.info("namespace_images_deleted", namespace=namespace, count=count)
        return count

    async def url(self, namespace: str, image_id: str, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/images/{namespace}/{image_id}"

    async def close(self) -> None:
        pass
