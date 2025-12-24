# Frontend Agent - Dockerfile
FROM python:3.11-slim

# Metadata
LABEL maintainer="Crypto Trading System"
LABEL description="Frontend Agent - Streamlit Dashboard"

# Set working directory
WORKDIR /app

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

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
