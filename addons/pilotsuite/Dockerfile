ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.21
FROM $BUILD_FROM

# Install only the packages actually needed by the current add-on payload.
RUN apk add --no-cache python3 py3-pip

# Copy application from the add-on's own rootfs so the published add-on folder is self-contained
COPY rootfs/usr/src/app /app
WORKDIR /app

# Install Python requirements
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Expose API port
EXPOSE 8909

CMD ["python3", "main.py"]
