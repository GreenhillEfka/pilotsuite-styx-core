#!/usr/bin/with-contenv bashio
set -e
bashio::log.info "Starting PilotSuite Platinum v17.0.0..."
python3 /usr/src/app/main.py
