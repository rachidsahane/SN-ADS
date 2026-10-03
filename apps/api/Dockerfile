# syntax=docker/dockerfile:1.7
# Build context: the repository root (so later phases can COPY data/seed).
#   docker build -f apps/api/Dockerfile --target dev  .   (local: tools, hot reload)
#   docker build -f apps/api/Dockerfile --target prod .   (staging and production)
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.5.31@sha256:7bff3c3776ec467fc1437960f2c469d8beb30f536a6465a3350c647ccd260ec2

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:${PATH}" \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
# libgomp1: OpenMP runtime required by the XGBoost wheel.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app

FROM base AS deps-prod
COPY --from=uv /uv /usr/local/bin/uv
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

FROM base AS deps-dev
COPY --from=uv /uv /usr/local/bin/uv
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Local only: runs as root so the bind-mounted source and tool caches stay writable.
FROM base AS dev
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=deps-dev /opt/venv /opt/venv
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/app", "--no-access-log", "--no-server-header"]

FROM base AS prod
COPY --from=deps-prod /opt/venv /opt/venv
COPY apps/api/app ./app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log", "--no-server-header"]
