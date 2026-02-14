from src.config import Settings, settings


class TestConfigDefaults:
    def test_app_name(self) -> None:
        assert settings.app_name == "image-serving-service"

    def test_debug_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.debug is False

    def test_port_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.port == 8000

    def test_host_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.host == "0.0.0.0"

    def test_log_level_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.log_level == "info"

    def test_cors_origins_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.cors_origins == ["*"]

    def test_metrics_enabled_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.metrics_enabled is True

    def test_max_upload_size(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.max_upload_size == 1200

    def test_max_fetch_size(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.max_fetch_size == 800

    def test_max_fetch_bytes(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.max_fetch_bytes == 10485760

    def test_fetch_timeout(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.fetch_timeout == 15.0

    def test_proxies_default_empty(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.proxies == {}

    def test_proxy_files_default_empty(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.proxy_files == {}

    def test_proxy_strategy_default(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.proxy_strategy == "round-robin"

    def test_fetch_max_retries(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.fetch_max_retries == 3

    def test_proxy_blacklist_threshold(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.proxy_blacklist_threshold == 3

    def test_proxy_blacklist_ttl(self) -> None:
        s = Settings(uploads_path="/tmp/test")
        assert s.proxy_blacklist_ttl == 300.0
