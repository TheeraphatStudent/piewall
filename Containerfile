# syntax=docker/dockerfile:1
# piewall MCP server, read-only "file mode" over a rules JSON exported on Windows.
# A container cannot reach the Windows host firewall, so live mode is not available here.
#
#   podman build -t piewall -f Containerfile .        (or: docker build -f Containerfile .)
#   podman run -i --rm -v ./rules.json:/data/rules.json:ro piewall
#   podman run --rm -p 8000:8000 -v ./rules.json:/data/rules.json:ro \
#       -e PIEWALL_TRANSPORT=streamable-http -e PIEWALL_HOST=0.0.0.0 piewall   # http://localhost:8000/mcp

ARG PYTHON_IMAGE=docker.io/library/python:3.12-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.8

FROM ${UV_IMAGE} AS uv

# ---- build: resolve runtime deps from uv.lock into /app/.venv ------------------------------
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first (cached layer), then the project itself; non-editable so /src is not needed later.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---- runtime ------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE}
ARG VERSION=dev
LABEL org.opencontainers.image.title="piewall" \
      org.opencontainers.image.description="piewall MCP server: read-only analysis of exported Windows Firewall rules" \
      org.opencontainers.image.source="https://github.com/TheeraphatStudent/piewall" \
      org.opencontainers.image.url="https://piewall.th33raphat.dev" \
      org.opencontainers.image.documentation="https://github.com/TheeraphatStudent/piewall/blob/main/docker/README.md" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Theeraphat" \
      org.opencontainers.image.version="${VERSION}"

RUN groupadd --gid 10001 piewall \
 && useradd --no-create-home --uid 10001 --gid piewall --home-dir /app --shell /usr/sbin/nologin piewall \
 && mkdir -p /data && chown piewall:piewall /data
COPY --from=build --chown=root:root /app/.venv /app/.venv

WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIEWALL_RULES_FILE=/data/rules.json \
    PIEWALL_TRANSPORT=stdio \
    PIEWALL_PORT=8000
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["piewall-mcp"]
