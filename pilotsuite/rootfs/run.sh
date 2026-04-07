#!/usr/bin/with-contenv bashio
set -e
bashio::log.info "Starting PilotSuite Core v16.3.0..."
python3 /usr/src/app/main.py
