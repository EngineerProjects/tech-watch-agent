# Tech Watch Agent - Multi-stage Build Dockerfile

ARG PYTHON_VERSION=3.11

# Stage 1: Builder
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and package sources required for installation
COPY pyproject.toml README.md ./
COPY app ./app

# Install dependencies
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

# Security: Run as non-root user
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Create directories
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Copy application code (before this, ensure .dockerignore excludes unnecessary files)
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER appuser

EXPOSE 8000

# Default command
CMD ["python", "-m", "app.main", "--mode", "api"]
