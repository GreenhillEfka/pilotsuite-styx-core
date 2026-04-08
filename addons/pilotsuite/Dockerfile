ARG BUILD_FROM
FROM $BUILD_FROM

# Copy everything from addon directory
COPY . /app

# Working directory is /app (contains app/main.py, app/copilot_core/, etc.)
WORKDIR /app/app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose API port
EXPOSE 8909

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Start application (main.py is in /app/app/)
CMD ["python3", "main.py"]
