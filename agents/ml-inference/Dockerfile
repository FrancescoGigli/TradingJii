FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create shared directory
RUN mkdir -p /app/shared/data_cache /app/shared/models

# Set environment variable
ENV PYTHONUNBUFFERED=1

# Run the inference agent
CMD ["python", "main.py"]
