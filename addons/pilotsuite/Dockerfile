ARG BUILD_FROM
FROM $BUILD_FROM

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY app/requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Expose API port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Start application
CMD ["python3", "main.py"]
