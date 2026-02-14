# Image Serving Service

[![CI](https://github.com/galthran-wq/image-serving-service/actions/workflows/ci.yml/badge.svg)](https://github.com/galthran-wq/image-serving-service/actions/workflows/ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/galthran-wq/image-serving-service/badge.svg?branch=master)](https://coveralls.io/github/galthran-wq/image-serving-service?branch=master)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type_checker-mypy-blue)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Microservice for uploading, serving, and fetching images with proxy-based external fetching.

## Stack

- **FastAPI** — async web framework
- **uv** — package manager
- **Pydantic v2** — validation and settings
- **structlog** — structured logging
- **Pillow** — image processing and resizing
- **resilient-httpx** — HTTP client with proxy rotation, retry, and named pools
- **Prometheus** — metrics via prometheus-fastapi-instrumentator
- **pytest + httpx** — testing
- **ruff** — linting and formatting
- **mypy** — type checking
- **Docker** — containerization

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/images/{namespace}/{image_id}` | Serve a stored image |
| `POST` | `/images/{namespace}` | Upload a base64-encoded image |
| `DELETE` | `/images/{namespace}` | Delete all images in a namespace |
| `POST` | `/images/fetch` | Fetch an external image via proxy, return base64 |
| `POST` | `/images/{namespace}/proxy` | Fetch and save multiple external images, return URLs |
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness check |

## Quick Start

```bash
make install
make run
```

## Commands

| Command | Description |
|---|---|
| `make install` | Install dependencies |
| `make run` | Run dev server with hot reload |
| `make test` | Run tests with coverage |
| `make lint` | Run ruff + mypy |
| `make format` | Auto-format code |
| `make pre-commit` | Install pre-commit hooks |
| `make docker-build` | Build Docker image |
| `make docker-run` | Run Docker container |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `UPLOADS_PATH` | `/app/uploads` | Base storage directory |
| `MAX_UPLOAD_SIZE` | `1200` | Max pixel dimension for uploaded images |
| `MAX_FETCH_SIZE` | `800` | Max pixel dimension for fetched images |
| `MAX_FETCH_BYTES` | `10485760` | Max response size in bytes for external fetches |
| `FETCH_TIMEOUT` | `15.0` | Timeout for external image fetches |
| `PROXIES` | `{}` | Named proxy pools as inline URLs, e.g. `{"foreign": ["http://p1:8080"]}` |
| `PROXY_FILES` | `{}` | Named proxy pools as file paths, e.g. `{"foreign": "/app/proxies_foreign.txt"}` |
| `PROXY_STRATEGY` | `round-robin` | Proxy rotation strategy |
| `FETCH_MAX_RETRIES` | `3` | Max retry attempts for fetching |
| `PROXY_BLACKLIST_THRESHOLD` | `3` | Consecutive failures before blacklisting a proxy |
| `PROXY_BLACKLIST_TTL` | `300.0` | Seconds to blacklist a proxy |

## Project Structure

```
src/
├── main.py           — app factory, structlog config, Prometheus setup
├── config.py         — pydantic-settings based configuration
├── dependencies.py   — FastAPI dependency injection providers
├── api/
│   ├── router.py     — aggregated API router
│   └── endpoints/
│       ├── health.py — health/readiness checks
│       └── images.py — image upload, serve, delete, fetch
├── schemas/
│   ├── health.py     — health response model
│   └── images.py     — image request/response models
├── services/
│   ├── image_hosting.py  — save, serve, delete images on disk
│   └── image_fetcher.py  — fetch external images via resilient-httpx
└── core/
    ├── exceptions.py — custom exceptions + handlers
    └── middleware.py  — CORS, request logging, request ID
```
