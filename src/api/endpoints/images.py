import base64
import ipaddress
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from src.core.exceptions import AppError
from src.schemas.images import (
    ImageDeleteResponse,
    ImageFetchRequest,
    ImageFetchResponse,
    ImageUploadRequest,
    ImageUploadResponse,
)
from src.services import image_fetcher, image_hosting

logger = structlog.get_logger()

router = APIRouter(prefix="/images")


def _validate_path_segment(value: str, name: str) -> None:
    if not value or ".." in value or "/" in value:
        raise AppError(status_code=400, detail=f"Invalid {name}")


def _is_blocked_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def _validate_fetch_url(url: str) -> None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise AppError(status_code=400, detail="Invalid url")
    if not parsed.hostname:
        raise AppError(status_code=400, detail="Invalid url")
    hostname = parsed.hostname
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise AppError(status_code=400, detail="Invalid url")
    if _is_blocked_ip(hostname):
        raise AppError(status_code=400, detail="Invalid url")


@router.post("/fetch", response_model=ImageFetchResponse)
async def fetch_external_image(body: ImageFetchRequest) -> ImageFetchResponse:
    _validate_fetch_url(body.url)

    image_bytes = await image_fetcher.fetch_image(body.url, pool=body.pool)
    if not image_bytes:
        raise AppError(status_code=502, detail="Failed to fetch external image")

    mime_type = image_hosting.detect_mime_type(image_bytes)
    data = base64.b64encode(image_bytes).decode()
    return ImageFetchResponse(data=data, mime_type=mime_type)


@router.get("/{namespace}/{image_id}")
async def get_image(namespace: str, image_id: str) -> FileResponse:
    _validate_path_segment(namespace, "namespace")
    _validate_path_segment(image_id, "image_id")

    result = image_hosting.get_image_path(namespace, image_id)
    if not result:
        raise AppError(status_code=404, detail="Image not found")

    image_path, media_type = result
    return FileResponse(
        path=image_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/{namespace}", response_model=ImageUploadResponse)
async def upload_image(namespace: str, request: Request, body: ImageUploadRequest) -> ImageUploadResponse:
    _validate_path_segment(namespace, "namespace")

    base_url = str(request.base_url).rstrip("/")
    image_id = image_hosting.save_image(namespace, body.data)
    if not image_id:
        raise AppError(status_code=500, detail="Failed to save image")

    url = image_hosting.get_image_url(namespace, image_id, base_url)
    return ImageUploadResponse(image_id=image_id, url=url)


@router.delete("/{namespace}", response_model=ImageDeleteResponse)
async def delete_images(namespace: str) -> ImageDeleteResponse:
    _validate_path_segment(namespace, "namespace")

    count = image_hosting.delete_namespace_images(namespace)
    return ImageDeleteResponse(deleted_count=count)
