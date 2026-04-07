ARG BUILD_FROM
FROM ${BUILD_FROM}

# Installiere Python und Abhängigkeiten
RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY rootfs /app/

# Port für PilotSuite Core
EXPOSE 8909

# Start-Skript ausführbar machen
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
