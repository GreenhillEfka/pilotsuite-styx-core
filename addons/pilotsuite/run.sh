#!/bin/bash
set -e
echo "PilotSuite Core v16.0.0 starting..."
export PILOTSUITE_VERSION="16.0.0"
export PILOTSUITE_PORT="8909"
export PILOTSUITE_HOST="localhost"
exec python3 -m uvicorn copilot_core.api.rest_server:app --host 0.0.0.0 --port 8909 --workers 4
