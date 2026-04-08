ARG BUILD_FROM
FROM $BUILD_FROM

# Copy everything from addon directory
COPY . /app

# Working directory where main.py lives
WORKDIR /app/app

# Install system dependencies first
RUN apk add --no-cache python3 py3-pip

# Install Python packages via pip (not apk - some don't exist)
RUN pip3 install --no-cache-dir \
    aiohttp \
    fastapi \
    uvicorn \
    pydantic \
    requests \
    numpy \
    scipy

# Expose API port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Start application
CMD ["python3", "main.py"]
