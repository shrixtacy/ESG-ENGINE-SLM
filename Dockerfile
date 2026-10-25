# ============================================================
# ESGPilot — API Service Dockerfile
# Multi-stage build: builder + slim runtime
#
# Build:  docker build -t esgpilot-api:latest .
# Run:    docker run -p 8080:8080 --env-file .env esgpilot-api:latest
#
# GPU variant: see docker-compose.yml (gpu profile)
# ============================================================

# ── Stage 1: Builder ─────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for building native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a prefix for easy copy
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY api/         ./api/
COPY rules/       ./rules/
COPY ingestion/   ./ingestion/
COPY kb/          ./kb/

# Create non-root user for security
RUN useradd --system --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

# Use exec form — no shell to avoid signal handling issues
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "info"]
