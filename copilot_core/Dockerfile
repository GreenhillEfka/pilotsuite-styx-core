ARG BUILD_FROM
FROM $BUILD_FROM

# ── Required Home Assistant add-on labels ────────────────────────────────────
ARG BUILD_ARCH
ARG BUILD_VERSION
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="addon" \
    io.hass.arch="${BUILD_ARCH}"

# ── Install runtime + build deps, pip packages, then clean build deps ────────
RUN apk add --no-cache \
        python3 py3-pip graphviz curl bash libstdc++ libgcc \
        # Build deps needed for psutil and numpy C extensions
        gcc g++ musl-dev python3-dev linux-headers && \
    pip3 install --no-cache-dir --break-system-packages --prefer-binary \
        flask==3.0.2 \
        flask-compress==1.14 \
        waitress==3.0.0 \
        python-ulid==2.7.0 \
        pyyaml==6.0.1 \
        psutil==6.1.0 \
        neo4j==5.26.0 \
        pydantic==2.12.5 \
        requests==2.31.0 \
        qrcode==8.0 \
        numpy && \
    # Remove build deps to keep image small
    apk del gcc g++ musl-dev python3-dev linux-headers

# ── Ollama (optional — LLM features) ────────────────────────────────────────
# Try Alpine edge package first, fall back to binary download
RUN echo "@edge-community https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories && \
    (apk add --no-cache ollama@edge-community 2>/dev/null || \
     (echo "INFO: edge package unavailable, trying binary download..." && \
      apk add --no-cache gcompat && \
      ARCH=$(uname -m) && \
      case "$ARCH" in \
        x86_64) DLARCH="amd64" ;; \
        aarch64) DLARCH="arm64" ;; \
        *) echo "ERROR: Unsupported arch $ARCH"; exit 1 ;; \
      esac && \
      curl -fsSL --retry 3 --retry-delay 2 \
        "https://ollama.com/download/ollama-linux-${DLARCH}.tgz" | tar xz -C /usr)) || \
    echo "WARNING: Ollama installation failed -- LLM features will be unavailable"

# Persist Ollama models in /share/ (NOT /data/) to avoid bloating HA backups
ENV OLLAMA_MODELS=/share/pilotsuite/ollama/models
# Export add-on build version into runtime for API/banner version reporting
ENV COPILOT_VERSION=${BUILD_VERSION}

# ── Application ──────────────────────────────────────────────────────────────
WORKDIR /usr/src/app
COPY rootfs/usr/src/app /usr/src/app

EXPOSE 8909

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -sf http://localhost:8909/health || exit 1

COPY rootfs/usr/src/app/start_dual.sh /start.sh
RUN chmod +x /start.sh
CMD ["/start.sh"]
