"""
PilotSuite Core Configuration

Central configuration for connection pooling, timeouts, and performance settings.
"""

import os

# ---------------------------------------------------------------------------
# Connection Pool Configuration
# ---------------------------------------------------------------------------

# Maximum number of connections in the pool (per target: HA, Ollama)
POOL_MAX_CONNECTIONS = int(os.environ.get("POOL_MAX_CONNECTIONS", "10"))

# Connection timeout in seconds
POOL_TIMEOUT = int(os.environ.get("POOL_TIMEOUT", "30"))

# Health check interval in seconds
POOL_HEALTH_CHECK_INTERVAL = int(os.environ.get("POOL_HEALTH_CHECK_INTERVAL", "60"))

# TCP connector TTL (connection recycling)
POOL_CONNECTOR_TTL = int(os.environ.get("POOL_CONNECTOR_TTL", "300"))

# ---------------------------------------------------------------------------
# HA-Supervisor Configuration
# ---------------------------------------------------------------------------

# HA-Supervisor API URL
SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")

# HA-Supervisor API Token
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# HA-Supervisor request timeout (seconds)
HA_TIMEOUT = int(os.environ.get("HA_TIMEOUT", "10"))

# ---------------------------------------------------------------------------
# Ollama Configuration
# ---------------------------------------------------------------------------

# Ollama API URL
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Ollama model to use
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")

# Ollama request timeout (seconds)
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Cloud Fallback Configuration
# ---------------------------------------------------------------------------

# Cloud API URL (OpenAI-compatible /v1 endpoint)
CLOUD_API_URL = os.environ.get("CLOUD_API_URL", "")

# Cloud API Key
CLOUD_API_KEY = os.environ.get("CLOUD_API_KEY", "")

# Cloud model to use
CLOUD_MODEL = os.environ.get("CLOUD_MODEL", "gpt-4o-mini")

# Prefer local (Ollama) over cloud
PREFER_LOCAL = os.environ.get("PREFER_LOCAL", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Performance Settings
# ---------------------------------------------------------------------------

# LLM call rate limiting
LLM_MAX_CALLS_PER_HOUR = int(os.environ.get("LLM_MAX_CALLS_PER_HOUR", "60"))

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(
    os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(
    os.environ.get("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")
)

# ---------------------------------------------------------------------------
# Pool Configuration Dictionary (for easy passing)
# ---------------------------------------------------------------------------

POOL_CONFIG = {
    "max_connections": POOL_MAX_CONNECTIONS,
    "timeout": POOL_TIMEOUT,
    "health_check_interval": POOL_HEALTH_CHECK_INTERVAL,
    "connector_ttl": POOL_CONNECTOR_TTL,
}

HA_CONFIG = {
    "url": SUPERVISOR_API,
    "token": SUPERVISOR_TOKEN,
    "timeout": HA_TIMEOUT,
}

OLLAMA_CONFIG = {
    "url": OLLAMA_URL,
    "model": OLLAMA_MODEL,
    "timeout": OLLAMA_TIMEOUT,
}

CLOUD_CONFIG = {
    "url": CLOUD_API_URL,
    "key": CLOUD_API_KEY,
    "model": CLOUD_MODEL,
}


def get_pool_config() -> dict:
    """Return connection pool configuration."""
    return POOL_CONFIG.copy()


def get_ha_config() -> dict:
    """Return HA-Supervisor configuration."""
    return HA_CONFIG.copy()


def get_ollama_config() -> dict:
    """Return Ollama configuration."""
    return OLLAMA_CONFIG.copy()


def get_cloud_config() -> dict:
    """Return cloud fallback configuration."""
    return CLOUD_CONFIG.copy()
