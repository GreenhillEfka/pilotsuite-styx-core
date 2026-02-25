#!/bin/bash
# PilotSuite Core startup with embedded Ollama support (alternative script)
# Use start_dual.sh as the primary startup script.

set -e

export HOME="${HOME:-/tmp}"
mkdir -p "$HOME" 2>/dev/null || true

echo "Starting PilotSuite Core..."

# Ensure model persistence
export OLLAMA_MODELS=${OLLAMA_MODELS:-/share/pilotsuite/ollama/models}
mkdir -p "$OLLAMA_MODELS"

FALLBACK_MODEL="qwen3:0.6b"
MODEL=${OLLAMA_MODEL:-qwen3:0.6b}
NEED_OLLAMA=${CONVERSATION_ENABLED:-true}
case "${NEED_OLLAMA}" in
    1|true|yes|on|TRUE|YES|ON) NEED_OLLAMA="true" ;;
    *) NEED_OLLAMA="false" ;;
esac
OLLAMA_PID=""
MODEL_PULL_PID=""

cleanup() {
    if [ -n "$MODEL_PULL_PID" ]; then
        kill "$MODEL_PULL_PID" 2>/dev/null || true
        wait "$MODEL_PULL_PID" 2>/dev/null || true
    fi
    if [ -n "$OLLAMA_PID" ]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

pull_models_worker() {
    (
        ATTEMPTS=0
        MAX_ATTEMPTS=720  # ~1h
        until curl -sf -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; do
            ATTEMPTS=$((ATTEMPTS + 1))
            if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
                echo "WARNING: Model pull worker timed out waiting for Ollama"
                exit 0
            fi
            sleep 5
        done

        echo "Ensuring fallback model $FALLBACK_MODEL..."
        ollama pull "$FALLBACK_MODEL" || echo "WARNING: Failed to pull fallback $FALLBACK_MODEL"

        if [ "$MODEL" != "$FALLBACK_MODEL" ]; then
            echo "Ensuring configured model $MODEL..."
            ollama pull "$MODEL" || echo "WARNING: Failed to pull configured model $MODEL"
        fi
    ) &
    MODEL_PULL_PID=$!
}

if [ "$NEED_OLLAMA" = "true" ]; then
    echo "Checking Ollama..."

    if ! command -v ollama >/dev/null 2>&1; then
        echo "ERROR: Ollama binary missing while conversation is enabled"
        exit 1
    fi

    if ! curl -sf -m 3 http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Starting Ollama service..."

        ollama serve &
        OLLAMA_PID=$!
        sleep 1
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "ERROR: Ollama failed to start while conversation is enabled"
            exit 1
        fi
    else
        echo "Ollama already running"
    fi

    # Non-blocking model pull; API starts immediately.
    pull_models_worker
fi

echo "Starting PilotSuite Core API on port ${PORT:-8909}..."
exec python3 -u main.py
