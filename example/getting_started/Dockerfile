# Dockerfile for Tavern Getting Started Examples
# This demonstrates how to containerize Tavern tests for CI/CD

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user
RUN useradd --create-home --shell /bin/bash tavern && \
    chown -R tavern:tavern /app
USER tavern

# Expose the port the test server runs on
EXPOSE 5000

# Default command to run tests
CMD ["python", "-m", "pytest", "test_basic_api.tavern.yaml", "-v"]
