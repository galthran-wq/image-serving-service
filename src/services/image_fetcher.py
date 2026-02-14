from pathlib import Path

import structlog
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
    for line in file_path.read_text(encoding="utf-8").splitlines():
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


async def fetch_image(url: str, pool: str | None = None) -> bytes | None:
    client = get_http_client()
    try:
        async with client.stream("GET", url, pool=pool) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > settings.max_fetch_bytes:
                raise ValueError("response_too_large")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > settings.max_fetch_bytes:
                    raise ValueError("response_too_large")
        return bytes(data)
    except Exception as e:
        logger.error("image_fetch_failed", url=url, error=str(e))
        return None


async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
