ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG BUILD_VERSION
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="addon" \
    io.hass.arch="${BUILD_ARCH}"

WORKDIR /app

COPY app/requirements.txt /tmp/requirements.txt

RUN apk add --no-cache \
        python3 py3-pip bash curl libstdc++ libgcc \
        gcc g++ musl-dev python3-dev linux-headers && \
    pip3 install --no-cache-dir --break-system-packages --prefer-binary \
        -r /tmp/requirements.txt && \
    apk del gcc g++ musl-dev python3-dev linux-headers

COPY . /app

WORKDIR /app/app

# Create persistent data directory
RUN mkdir -p /data && chmod 755 /data

# Set environment variable for data storage
ENV DATA_DIR=/data
ENV PYTHONPATH=/app/app
ENV COPILOT_VERSION=${BUILD_VERSION}

# Expose API port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Start application
CMD ["python3", "main.py"]
