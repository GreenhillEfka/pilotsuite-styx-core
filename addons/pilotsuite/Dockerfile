ARG BUILD_FROM
FROM $BUILD_FROM

# Set version
ENV PILOTSUITE_VERSION=1.0.2
ENV PILOTSUITE_PORT=8909

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    redis \
    && rm -rf /var/cache/apk/*

# Copy application code
COPY copilot_core /app/copilot_core
COPY requirements.txt /app/

WORKDIR /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8909/health || exit 1

# Run application
CMD ["python3", "-m", "uvicorn", "copilot_core.api.rest_server:app", "--host", "0.0.0.0", "--port", "8909"]
