# Precog Docker Image for Railway Deployment
# Uses Python 3.12 slim image for minimal size
#
# Railway will automatically detect this Dockerfile and use it for builds.
# The src/ layout requires pip install to make the precog package importable.
#
# Build: docker build -t precog .
# Run locally: docker run -e DATABASE_URL=... precog

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Install system dependencies
# - gcc for compiling some Python packages
# - libpq-dev for psycopg2
# - git for version tracking (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the package configuration
COPY pyproject.toml .

# Copy source code
COPY src/ src/
COPY main.py .

# Install the package in editable mode so imports work
# This makes 'from precog.xxx import yyy' work correctly
RUN pip install --no-cache-dir -e .

# Note: Configuration files are in src/precog/config/ and copied with src/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Default command - can be overridden by Railway service settings
# For CLI tool, this just shows help
CMD ["python", "main.py", "--help"]
