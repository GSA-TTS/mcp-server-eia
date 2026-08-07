# syntax=docker/dockerfile:1

# Container image for the EIA MCP server, hosted by the Obot MCP gateway as a
# `containerized` server. It serves MCP over streamable HTTP at :8080/mcp with a
# /health readiness endpoint (see src/eia_mcp/app.py + routes.py).
#
# SECURITY: no credentials are baked into the image. The per-user EIA_API_KEY is
# injected as an environment variable at runtime by the gateway (singleUser
# deployment). See .dockerignore — .env is never copied in.

FROM python:3.14-slim

# uv for fast, lockfile-faithful dependency installation.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Serve over HTTP on 8080 (matches the catalog containerizedConfig).
    PORT=8080 \
    # Install into a project-local venv and put it on PATH.
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (cached) using only the lock + manifest, so code
# changes don't bust the dependency layer. --frozen fails if uv.lock is stale.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the source and install the project itself.
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8080

# PORT=8080 selects HTTP transport at /mcp (see app.py transport selection).
CMD ["python", "-m", "eia_mcp.app"]
