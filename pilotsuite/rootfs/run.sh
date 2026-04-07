#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting PilotSuite Platinum Core..."
cd /usr/src/app
python3 main.py
