# Data Fetcher Agent - Dockerfile
FROM python:3.11-slim

# Metadata
LABEL maintainer="Crypto Trading System"
LABEL description="Data Fetcher Agent - Download OHLCV from Bybit"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create shared data directory
RUN mkdir -p /app/shared/data_cache

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SHARED_DATA_PATH=/app/shared

# Default command
CMD ["python", "main.py"]
