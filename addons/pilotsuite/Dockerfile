ARG BUILD_FROM
FROM $BUILD_FROM

# Set version
ENV PILOTSUITE_VERSION=16.0.0
ENV PILOTSUITE_PORT=8909

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-uvicorn \
    py3-fastapi \
    && rm -rf /var/cache/apk/*

# Copy application
COPY . /app
WORKDIR /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt 2>/dev/null || true

# Expose port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8909/health || exit 1

# Run application
CMD ["python3", "-m", "uvicorn", "copilot_core.api.rest_server:app", "--host", "0.0.0.0", "--port", "8909"]
