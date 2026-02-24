#!/bin/sh
# PilotSuite Core + Ollama startup script
# Ollama is bundled in the addon for offline LLM support.
# Models are persisted in /share/ (NOT /data/) to avoid bloating HA backups.
#
# Model strategy:
#   - qwen3:0.6b (400MB) is ALWAYS pulled (obligatory, guarantees offline AI)
#   - qwen3:4b (2.5GB) is optional for higher quality (pulled if configured)

set -e

# Ensure HOME exists for Ollama runtime; some base images do not define it.
export HOME="${HOME:-/tmp}"
mkdir -p "$HOME" 2>/dev/null || true

CORE_VERSION="${COPILOT_VERSION:-${BUILD_VERSION:-$(cat /usr/src/app/VERSION 2>/dev/null || echo 0.0.0)}}"
export COPILOT_VERSION="$CORE_VERSION"

echo "============================================"
echo "  PilotSuite v${CORE_VERSION} -- Styx"
echo "  Die Verbindung beider Welten"
echo "  Local AI for your Smart Home"
echo "============================================"

# ---------------------------------------------------------------------------
# Bridge: Read /data/options.json and export env vars
# ---------------------------------------------------------------------------
OPTIONS_FILE="/data/options.json"
if [ -f "$OPTIONS_FILE" ]; then
    echo "Loading addon configuration from $OPTIONS_FILE..."

    eval "$(python3 -c "
import json, os
try:
    with open('$OPTIONS_FILE') as f:
        opts = json.load(f)
    pairs = {
        'OLLAMA_URL': opts.get('conversation_ollama_url', ''),
        'OLLAMA_MODEL': opts.get('conversation_ollama_model', ''),
        'CLOUD_API_URL': opts.get('conversation_cloud_api_url', ''),
        'CLOUD_API_KEY': opts.get('conversation_cloud_api_key', ''),
        'CLOUD_MODEL': opts.get('conversation_cloud_model', ''),
        'PREFER_LOCAL': str(opts.get('conversation_prefer_local', True)).lower(),
        'CONVERSATION_ENABLED': str(opts.get('conversation_enabled', True)).lower(),
        'ASSISTANT_NAME': opts.get('conversation_assistant_name', ''),
    }
    ll = opts.get('log_level', '')
    if ll:
        pairs['LOG_LEVEL'] = ll
    at = opts.get('auth_token', '')
    if at:
        pairs['AUTH_TOKEN'] = at

    for k, v in pairs.items():
        if v:
            print(f'export {k}=\"{v}\"')
except Exception as e:
    print(f'echo \"WARNING: Could not parse options.json: {e}\"', flush=True)
" 2>/dev/null)" || echo "WARNING: Config bridge failed, using defaults"
else
    echo "No $OPTIONS_FILE found (development mode), using env defaults"
fi

# ---------------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------------

# Internal Ollama port (avoids conflicts if host also runs Ollama on 11434)
INTERNAL_OLLAMA_PORT=${INTERNAL_OLLAMA_PORT:-11435}
INTERNAL_OLLAMA_URL="http://127.0.0.1:${INTERNAL_OLLAMA_PORT}"

# Determine Ollama URL: user-configured external, or internal bundled
CONFIGURED_URL="${OLLAMA_URL:-}"
CONV_ENABLED="${CONVERSATION_ENABLED:-true}"
case "${CONV_ENABLED}" in
    1|true|yes|on|TRUE|YES|ON) CONV_ENABLED="true" ;;
    *) CONV_ENABLED="false" ;;
esac

# Detect if user points to an external Ollama server
USE_INTERNAL_OLLAMA=true
if [ -n "$CONFIGURED_URL" ]; then
    case "$CONFIGURED_URL" in
        *localhost:${INTERNAL_OLLAMA_PORT}*|*127.0.0.1:${INTERNAL_OLLAMA_PORT}*)
            # Points to our internal instance
            USE_INTERNAL_OLLAMA=true
            ;;
        *localhost*|*127.0.0.1*)
            # Points to localhost but different port — rewrite to our internal port
            echo "INFO: Rewriting Ollama URL to internal port ${INTERNAL_OLLAMA_PORT}"
            export OLLAMA_URL="$INTERNAL_OLLAMA_URL"
            USE_INTERNAL_OLLAMA=true
            ;;
        *)
            # Points to external server (e.g. NAS, other machine)
            EXTERNAL_URL="${CONFIGURED_URL%/}"
            echo "INFO: External Ollama configured at $EXTERNAL_URL — testing reachability..."
            if curl -sf -m 3 "${EXTERNAL_URL}/api/tags" >/dev/null 2>&1; then
                echo "INFO: External Ollama is reachable"
                export OLLAMA_URL="$EXTERNAL_URL"
                USE_INTERNAL_OLLAMA=false
            else
                echo "WARNING: External Ollama unreachable at $EXTERNAL_URL — falling back to internal Ollama"
                export OLLAMA_URL="$INTERNAL_OLLAMA_URL"
                USE_INTERNAL_OLLAMA=true
            fi
            ;;
    esac
else
    # No URL configured, use internal
    export OLLAMA_URL="$INTERNAL_OLLAMA_URL"
fi

# Obligatory minimum model (always available, 400MB)
FALLBACK_MODEL="qwen3:0.6b"

# Configured default model (fast startup and low RAM footprint)
MODEL=${OLLAMA_MODEL:-qwen3:0.6b}

# Ensure model persistence directory exists
export OLLAMA_MODELS=${OLLAMA_MODELS:-/share/pilotsuite/ollama/models}
mkdir -p "$OLLAMA_MODELS" 2>/dev/null || echo "WARNING: Cannot create $OLLAMA_MODELS (is /share mounted?)"

if [ -n "${CLOUD_API_URL:-}" ] && [ -n "${CLOUD_API_KEY:-}" ]; then
    CLOUD_STATUS="configured"
else
    CLOUD_STATUS="disabled"
fi
echo "Configuration: model=$MODEL, ollama_url=${OLLAMA_URL}, internal=${USE_INTERNAL_OLLAMA}, cloud_fallback=${CLOUD_STATUS}"

# ---------------------------------------------------------------------------
# Ollama startup (only if using internal)
# ---------------------------------------------------------------------------

if [ "$USE_INTERNAL_OLLAMA" = "false" ]; then
    echo "External Ollama configured — starting API directly"
    exec python3 -u main.py
fi

# Check if Ollama binary is installed
if ! command -v ollama >/dev/null 2>&1; then
    if [ "$CONV_ENABLED" = "true" ]; then
        echo "ERROR: Ollama binary not found while conversation is enabled. Aborting startup."
        exit 1
    fi
    echo "WARNING: Ollama not found -- LLM features disabled, starting API only"
    exec python3 -u main.py
fi

# Tell Ollama to bind on our internal port
export OLLAMA_HOST="127.0.0.1:${INTERNAL_OLLAMA_PORT}"

echo "Starting Ollama service on port ${INTERNAL_OLLAMA_PORT} (models dir: $OLLAMA_MODELS)..."
ollama serve &
OLLAMA_PID=$!
MODEL_PULL_PID=""

# Verify Ollama process did not exit immediately.
sleep 1
if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
    if [ "$CONV_ENABLED" = "true" ]; then
        echo "ERROR: Ollama failed to start while conversation is enabled. Aborting startup."
        exit 1
    fi
    echo "WARNING: Ollama failed to start, continuing without local LLM runtime"
    exec python3 -u main.py
fi

# Cleanup on exit
cleanup() {
    if [ -n "$MODEL_PULL_PID" ]; then
        kill "$MODEL_PULL_PID" 2>/dev/null || true
        wait "$MODEL_PULL_PID" 2>/dev/null || true
    fi
    echo "Shutting down Ollama (PID $OLLAMA_PID)..."
    kill "$OLLAMA_PID" 2>/dev/null || true
    wait "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Non-blocking readiness check: never delay API startup for Ollama/model downloads.
READY=false
if curl -sf -m 1 "${INTERNAL_OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    echo "Ollama is ready."
    READY=true
else
    echo "Ollama warmup in progress; startup continues and model pulls run in background."
fi

# Model pull (idempotent)
pull_model() {
    TARGET_MODEL="$1"
    LABEL="$2"
    echo "Ensuring $LABEL model $TARGET_MODEL is available..."
    if ollama pull "$TARGET_MODEL" 2>&1; then
        echo "$LABEL model $TARGET_MODEL ready"
        return 0
    else
        echo "WARNING: Could not pull $LABEL model $TARGET_MODEL"
        return 1
    fi
}

model_pull_worker() {
    (
        # Continue waiting in background if Ollama was not ready within initial window.
        if [ "$READY" != "true" ]; then
            echo "Model pull worker: waiting for Ollama in background..."
            ATTEMPTS=0
            MAX_ATTEMPTS=720  # ~1h at 5s intervals
            until curl -sf -m 3 "${INTERNAL_OLLAMA_URL}/api/tags" >/dev/null 2>&1; do
                ATTEMPTS=$((ATTEMPTS + 1))
                if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
                    echo "WARNING: Model pull worker timed out waiting for Ollama"
                    exit 0
                fi
                sleep 5
            done
        fi

        pull_model "$FALLBACK_MODEL" "fallback" || true

        if [ "$MODEL" != "$FALLBACK_MODEL" ]; then
            if ! pull_model "$MODEL" "configured"; then
                echo "WARNING: Configured model pull failed ($MODEL). Fallback remains available."
            fi
        fi

        echo "Model pull worker finished."
    ) &
    MODEL_PULL_PID=$!
}

# Start model pulls in background so API startup is never blocked by long downloads.
model_pull_worker

echo ""
echo "Starting PilotSuite Core API on port ${PORT:-8909}..."
echo "Dashboard: http://localhost:${PORT:-8909}/"
echo "API Docs:  http://localhost:${PORT:-8909}/api/v1/docs/"
echo "Chat API:  http://localhost:${PORT:-8909}/v1/chat/completions"
echo "MCP:       http://localhost:${PORT:-8909}/mcp"
echo "============================================"
exec python3 -u main.py
