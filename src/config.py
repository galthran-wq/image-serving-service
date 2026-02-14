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

    uploads_path: str = "/app/uploads"
    max_upload_size: int = 1200
    max_fetch_size: int = 800
    fetch_timeout: float = 15.0
    proxies: dict[str, list[str]] = {}
    proxy_files: dict[str, str] = {}
    proxy_strategy: str = "round-robin"
    fetch_max_retries: int = 3
    proxy_blacklist_threshold: int = 3
    proxy_blacklist_ttl: float = 300.0


settings = Settings()
