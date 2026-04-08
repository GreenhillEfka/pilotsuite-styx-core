ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache python3 py3-pip py3-aiohttp py3-fastapi py3-uvicorn py3-pydantic py3-requests py3-numpy py3-scipy

# Copy application from the add-on's own rootfs so the published add-on folder is self-contained
COPY rootfs/usr/src/app /app
WORKDIR /app

# Install Python requirements
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose API port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import requests; requests.get('http://localhost:8909/health')" || exit 1

CMD ["python3", "main.py"]
