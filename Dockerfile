FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
ARG INSTALL_S3=false
RUN if [ "$INSTALL_S3" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra s3; \
    else \
      uv sync --frozen --no-dev --no-install-project; \
    fi

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY src/ src/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
