ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Install system dependencies
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev \
    && apk add --no-cache python3 py3-pip py3-aiohttp py3-fastapi py3-uvicorn py3-pydantic py3-requests py3-numpy py3-scipy \
    && apk del .build-deps

# Copy requirements
COPY app/requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application (includes copilot_core/ subfolder)
COPY app/ .

# Set Python path to include copilot_core
ENV PYTHONPATH=/app:/app/copilot_core

EXPOSE 8909

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

CMD ["python3", "main.py"]
