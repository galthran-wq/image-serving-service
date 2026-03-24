from typing import Any

import structlog

logger = structlog.get_logger()


class S3StorageBackend:
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        prefix: str = "images",
        proxy: str | None = None,
    ) -> None:
        import aioboto3
        from botocore.config import Config as BotoConfig

        self._bucket = bucket
        self._prefix = prefix
        self._session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._endpoint_url = endpoint_url
        self._boto_config = BotoConfig(proxies={"https": proxy, "http": proxy}) if proxy else None

    def _key(self, namespace: str, image_id: str, ext: str) -> str:
        return f"{self._prefix}/{namespace}/{image_id}.{ext}"

    def _client_ctx(self) -> Any:
        return self._session.client("s3", endpoint_url=self._endpoint_url, config=self._boto_config)

    async def ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        async with self._client_ctx() as client:
            try:
                await client.head_bucket(Bucket=self._bucket)
                logger.info("s3_bucket_exists", bucket=self._bucket)
            except ClientError:
                try:
                    await client.create_bucket(Bucket=self._bucket)
                    logger.info("s3_bucket_created", bucket=self._bucket)
                except ClientError as exc:
                    logger.warning("s3_bucket_create_failed", bucket=self._bucket, error=str(exc))

    async def save(self, namespace: str, image_id: str, data: bytes, ext: str) -> None:
        from src.services.image_hosting import FORMAT_TO_MEDIA_TYPE

        key = self._key(namespace, image_id, ext)
        content_type = FORMAT_TO_MEDIA_TYPE.get(ext, "image/jpeg")
        async with self._client_ctx() as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        logger.info("image_saved_s3", namespace=namespace, image_id=image_id, key=key)

    async def get(self, namespace: str, image_id: str) -> tuple[bytes, str] | None:
        from botocore.exceptions import ClientError

        from src.services.image_hosting import FORMAT_TO_MEDIA_TYPE

        async with self._client_ctx() as client:
            for ext in ("jpg", "png", "gif", "webp"):
                key = self._key(namespace, image_id, ext)
                try:
                    response = await client.get_object(Bucket=self._bucket, Key=key)
                except ClientError as exc:
                    error_code = exc.response.get("Error", {}).get("Code")
                    if error_code in ("NoSuchKey", "404"):
                        continue
                    raise
                data = await response["Body"].read()
                media_type = FORMAT_TO_MEDIA_TYPE.get(ext, "image/jpeg")
                return data, media_type
        return None

    async def delete_namespace(self, namespace: str) -> int:
        prefix = f"{self._prefix}/{namespace}/"
        count = 0
        async with self._client_ctx() as client:
            paginator = client.get_paginator("list_objects_v2")
            keys_to_delete: list[dict[str, str]] = []
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys_to_delete.append({"Key": obj["Key"]})
            if keys_to_delete:
                # delete_objects supports max 1000 keys per call
                for i in range(0, len(keys_to_delete), 1000):
                    batch = keys_to_delete[i : i + 1000]
                    await client.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": batch},
                    )
                    count += len(batch)
        logger.info("namespace_images_deleted_s3", namespace=namespace, count=count)
        return count

    async def url(self, namespace: str, image_id: str, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/images/{namespace}/{image_id}"

    async def close(self) -> None:
        pass
