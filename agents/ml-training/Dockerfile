# ML Training Agent Dockerfile
# ============================
# Runs XGBoost + Optuna training jobs from queue

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create shared directory structure
RUN mkdir -p /app/shared/models /app/shared/data_cache

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SHARED_DATA_PATH=/app/shared
ENV TRAINING_POLL_INTERVAL=30
ENV LOG_LEVEL=INFO

# Default command: run daemon
CMD ["python", "main.py"]
