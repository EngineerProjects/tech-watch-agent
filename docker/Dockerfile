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

# Copy only dependency metadata first so code changes do not invalidate
# the third-party dependency layer.
COPY pyproject.toml ./

RUN python - <<'PY' > /tmp/requirements.txt
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text())
for dependency in data["project"]["dependencies"]:
    print(dependency)
PY

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r /tmp/requirements.txt

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
