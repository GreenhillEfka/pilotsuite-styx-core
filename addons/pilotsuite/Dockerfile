FROM ghcr.io/home-assistant/amd64-base:latest

# Copy app directory
COPY . /app

# Set working directory
WORKDIR /app/app

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    curl \
    libstdc++ \
    libgcc

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages \
    aiohttp \
    fastapi \
    uvicorn \
    pydantic \
    requests \
    numpy \
    scipy \
    flask \
    flask-socketio \
    flask-compress \
    python-ulid \
    pyyaml \
    psutil \
    neo4j \
    python-dotenv \
    prometheus-client \
    python-socketio \
    qrcode

# Create data directory for persistence
RUN mkdir -p /data && chmod 755 /data

# Set environment variables
ENV DATA_DIR=/data
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Start application
CMD ["python3", "main.py"]
