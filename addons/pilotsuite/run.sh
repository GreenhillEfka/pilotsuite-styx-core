#!/usr/bin/with-contenv bashio
set -e

# Log startup
bashio::log.info "Starting PilotSuite Core v20.0.0..."

# Get configuration
LOG_LEVEL=$(bashio::config 'log_level')
OLLAMA_HOST=$(bashio::config 'ollama_host')
OLLAMA_PORT=$(bashio::config 'ollama_port')

# Export environment variables
export LOG_LEVEL="${LOG_LEVEL:-info}"
export OLLAMA_HOST="${OLLAMA_HOST:-localhost}"
export OLLAMA_PORT="${OLLAMA_PORT:-11434}"

# Start the application
cd /app
exec python3 main.py
