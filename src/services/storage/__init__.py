from src.services.storage.base import StorageBackend

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        from src.config import settings

        if settings.storage_backend == "s3":
            from src.services.storage.s3 import S3StorageBackend

            _storage = S3StorageBackend(
                bucket=settings.s3_bucket,
                region=settings.s3_region,
                endpoint_url=settings.s3_endpoint_url,
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
                prefix=settings.s3_prefix,
                proxy=settings.s3_proxy,
            )
        else:
            from src.services.storage.local import LocalStorageBackend

            _storage = LocalStorageBackend(uploads_path=settings.uploads_path)
    return _storage


async def close_storage() -> None:
    global _storage
    if _storage is not None:
        await _storage.close()
        _storage = None


__all__ = ["StorageBackend", "get_storage", "close_storage"]
