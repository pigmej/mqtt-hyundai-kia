# Multi-stage build for Hyundai MQTT integration service
# Stage 1: Build stage with full Python environment for dependency installation
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files and README
COPY pyproject.toml README.md ./

# Install dependencies to app directory for appuser access
RUN pip install --no-cache-dir --prefix /app/.local .

# Stage 2: Runtime stage with minimal dependencies
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

# Copy installed dependencies from builder stage
COPY --from=builder /app/.local /app/.local

# Copy application source code with proper ownership
COPY --chown=appuser:appuser . .

# Set PATH and PYTHONPATH to include installed packages
ENV PATH=/app/.local/bin:$PATH \
    PYTHONPATH=/app/.local/lib/python3.10/site-packages

# Switch to non-root user
USER appuser

# Health check to verify service readiness
# The service will create /tmp/service-ready after successful initialization
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import os; from pathlib import Path; p = Path('/tmp/service-ready'); exit(0 if p.exists() else 1)"

# Default command
CMD ["python", "main.py"]