# syntax=docker/dockerfile:1.7
###############################################################################
# LibraryMind — Multi-stage container image
#
# Stage 1 (builder): install dependencies into a clean virtual env.
# Stage 2 (runtime): copy only the virtual env + source. Non-root user.
###############################################################################

ARG PYTHON_VERSION=3.11-slim-bookworm

# =============================================================================
# Builder stage
# =============================================================================
FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Build-time system deps for native wheels (e.g. chromadb's hnswlib).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv ${VIRTUAL_ENV}

WORKDIR /build

# Copy only dependency manifests first to maximise Docker layer caching.
COPY pyproject.toml ./
COPY README.md ./

# Install runtime deps. We avoid `--editable` so the resulting venv is
# self-contained and portable to the runtime stage.
RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# =============================================================================
# Runtime stage
# =============================================================================
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

# Create a non-root user. Running as root inside a container is a needless
# attack-surface risk even in dev.
RUN groupadd --system --gid 1000 librarymind \
    && useradd --system --uid 1000 --gid librarymind --create-home librarymind

# Copy the pre-built virtual environment from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=librarymind:librarymind app ./app
COPY --chown=librarymind:librarymind scripts ./scripts

# Persist ChromaDB and any runtime data outside the image.
RUN mkdir -p /app/data/chroma \
    && chown -R librarymind:librarymind /app/data

USER librarymind

EXPOSE 8000

# Healthcheck hits the /health endpoint (Phase 7). Until then it will
# return a connection error, which is fine — `docker compose` will still
# start the container; the check just won't report "healthy" yet.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
