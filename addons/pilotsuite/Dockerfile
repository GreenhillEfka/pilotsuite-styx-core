ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.21
FROM $BUILD_FROM

# Install only the packages actually needed by the current add-on payload.
# The published main.py currently uses only the Python standard library, so we
# keep the HA base image externally-managed environment untouched and skip pip.
RUN apk add --no-cache python3

# Copy application from the add-on's own rootfs so the published add-on folder is self-contained
COPY rootfs/usr/src/app /app
WORKDIR /app

# Expose API port
EXPOSE 8909

CMD ["python3", "main.py"]
