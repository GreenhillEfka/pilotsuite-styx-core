FROM python:3.11-slim-bookworm

WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY copilot_core/ ./copilot_core/
COPY docs/ ./docs/

# Create data directory
RUN mkdir -p /data && chmod 777 /data

# Expose port
EXPOSE 8909

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8909/health || exit 1

# Run application
CMD ["python", "main.py"]
