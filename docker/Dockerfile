# Tech Watch Agent - Multi-stage Build Dockerfile

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir --prefix=/install -e .

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

# Security: Run as non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Create directories
RUN mkdir -p /app/logs /app/alembic && \
    chown -R appuser:appuser /app

# Copy application code (before this, ensure .dockerignore excludes unnecessary files)
COPY alembic ./alembic
COPY app ./app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER appuser

EXPOSE 8000

# Default command
CMD ["python", "-m", "app.main", "--mode", "api"]