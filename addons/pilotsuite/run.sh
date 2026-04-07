#!/bin/bash
set -e

echo "Starting PilotSuite Core v16.0.0..."

# Start Redis if needed
redis-server --daemonize yes 2>/dev/null || true

# Start the application
cd /config
exec python3 -m pilotcore
