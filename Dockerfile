# ==============================================================================
# Legal Knowledge Platform — Multi-stage Production Dockerfile
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build virtualenv and install dependencies
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create isolated virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy the pinned production dependency set before application source so Docker
# can reuse this layer when only code changes.
COPY pyproject.toml README.md ./
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY design/ ./design/

# The lock supplies all runtime dependencies.  Installing with --no-deps keeps
# the image repeatable even though pyproject.toml retains its compatibility
# ranges for library consumers.
RUN pip install --no-cache-dir --no-deps .

# ------------------------------------------------------------------------------
# Stage 2: Final minimal runtime image
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

LABEL maintainer="Legal Knowledge Platform Team"
LABEL version="0.2.1"
LABEL description="Legal Knowledge Platform — Evidence-Grounded Legal Q&A"

# Install system runtime requirements (poppler for PDF rendering, tesseract for OCR, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
    tesseract-ocr-vie \
    util-linux \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Create non-root user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -d /app appuser

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set runtime environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LEGAL_PLATFORM_HOST=0.0.0.0 \
    LEGAL_PLATFORM_PORT=8080 \
    LEGAL_PLATFORM_DATA_DIR=/app/storage

# Copy application assets and code
COPY --chown=appuser:appgroup pyproject.toml README.md ./
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup frontend/ ./frontend/
COPY --chown=appuser:appgroup design/ ./design/
COPY --chown=appuser:appgroup docker-entrypoint.sh /app/docker-entrypoint.sh

# Prepare the persistent mount point. The entrypoint starts as root only long
# enough to make an empty or host bind-mounted directory writable, then drops
# permanently to appuser before launching Python.
RUN mkdir -p /app/storage/db /app/storage/files && \
    chown -R appuser:appgroup /app/storage && \
    chmod 755 /app/docker-entrypoint.sh

# Expose HTTP API and Web UI port
EXPOSE 8080

# Healthcheck targeting the application health probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "legal_platform", "--host", "0.0.0.0", "--port", "8080"]
