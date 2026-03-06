from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "image-serving-service"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    cors_origins: list[str] = ["*"]
    metrics_enabled: bool = True

    storage_backend: Literal["local", "s3"] = "local"

    uploads_path: str = "/app/uploads"
    max_upload_size: int = 1200
    max_fetch_size: int = 800
    max_fetch_bytes: int = 10485760
    fetch_timeout: float = 15.0
    proxies: dict[str, list[str]] = {}
    proxy_files: dict[str, str] = {}
    proxy_strategy: str = "round-robin"
    fetch_max_retries: int = 3
    proxy_blacklist_threshold: int = 3
    proxy_blacklist_ttl: float = 300.0

    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_prefix: str = "images"
    s3_proxy: str | None = None


settings = Settings()
