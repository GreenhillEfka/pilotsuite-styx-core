ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Copy requirements and install
COPY app/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application (main.py + copilot_core/ package)
COPY app/ .

# Set Python path
ENV PYTHONPATH=/app

EXPOSE 8909

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import requests; r = requests.get('http://localhost:8909/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

CMD ["python3", "main.py"]
