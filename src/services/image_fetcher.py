import asyncio
from io import BytesIO
from pathlib import Path

import structlog
from PIL import Image
from resilient_httpx import ProxyHttpClient, RetryPolicy

from src.config import settings

logger = structlog.get_logger()

_client: ProxyHttpClient | None = None


def _load_proxies_from_file(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("proxy_file_not_found", path=path)
        return []
    proxies = []
    for line in file_path.read_text().splitlines():
        line = line.strip()
        if line:
            proxies.append(line)
    return proxies


def _build_proxy_pools() -> dict[str, list[str]]:
    pools: dict[str, list[str]] = {}
    for name, proxy_list in settings.proxies.items():
        pools.setdefault(name, []).extend(proxy_list)
    for name, file_path in settings.proxy_files.items():
        pools.setdefault(name, []).extend(_load_proxies_from_file(file_path))
    return {name: urls for name, urls in pools.items() if urls}


def get_http_client() -> ProxyHttpClient:
    global _client
    if _client is None:
        pools = _build_proxy_pools()
        _client = ProxyHttpClient(
            proxies=pools or None,
            proxy_strategy=settings.proxy_strategy,
            retry=RetryPolicy(max_attempts=settings.fetch_max_retries),
            timeout=settings.fetch_timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            blacklist_threshold=settings.proxy_blacklist_threshold,
            blacklist_ttl=settings.proxy_blacklist_ttl,
            fallback_to_direct=True,
        )
    return _client


def resize_image(image_bytes: bytes, max_size: int) -> bytes:
    try:
        img = Image.open(BytesIO(image_bytes))
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
        return buffer.getvalue()
    except Exception:
        return image_bytes


async def fetch_image(url: str, pool: str | None = None) -> bytes | None:
    client = get_http_client()
    try:
        response = await client.get(url, pool=pool)
        response.raise_for_status()
        return resize_image(response.content, settings.max_fetch_size)
    except Exception as e:
        logger.error("image_fetch_failed", url=url, error=str(e))
        return None


async def fetch_image_to_file(url: str, dest_path: str, pool: str | None = None) -> bool:
    data = await fetch_image(url, pool=pool)
    if data:
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    return False


async def fetch_many_to_files(
    url_path_pairs: list[tuple[str, str]],
    max_concurrent: int = 5,
    pool: str | None = None,
) -> list[bool]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _fetch(url: str, path: str) -> bool:
        async with semaphore:
            return await fetch_image_to_file(url, path, pool=pool)

    tasks = [_fetch(url, path) for url, path in url_path_pairs]
    return await asyncio.gather(*tasks)


async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
