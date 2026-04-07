"""
PilotSuite Core Configuration

Central configuration for connection pooling, timeouts, and performance settings.

This legacy flat module also exposes the structured ``copilot_core.config.*``
package surface. Some historical imports resolve this file first; adding a
package path keeps submodule imports like ``copilot_core.config.engine`` stable.
"""

from __future__ import annotations

import os
from pathlib import Path


_pkg_dir = Path(__file__).resolve().parent
__path__ = [str(_pkg_dir / "config")]  # type: ignore[assignment]

_repo_bridge_dir = _pkg_dir.parents[5] / "copilot_core" / "config"
_repo_bridge_path = str(_repo_bridge_dir)
if _repo_bridge_dir.is_dir() and _repo_bridge_path not in __path__:
    __path__.append(_repo_bridge_path)

# ---------------------------------------------------------------------------
# Connection Pool Configuration
# ---------------------------------------------------------------------------

# Maximum number of connections in the pool (per target: HA, Ollama)
POOL_MAX_CONNECTIONS = int(os.environ.get("POOL_MAX_CONNECTIONS", "25"))

# Maximum connections per host (prevents connection starvation)
POOL_MAX_CONNECTIONS_PER_HOST = int(os.environ.get("POOL_MAX_CONNECTIONS_PER_HOST", "5"))

# Connection timeout in seconds
POOL_TIMEOUT = int(os.environ.get("POOL_TIMEOUT", "30"))

# Health check interval in seconds
POOL_HEALTH_CHECK_INTERVAL = int(os.environ.get("POOL_HEALTH_CHECK_INTERVAL", "60"))

# TCP connector TTL (connection recycling)
POOL_CONNECTOR_TTL = int(os.environ.get("POOL_CONNECTOR_TTL", "180"))

# DNS cache TTL (faster DNS resolution)
POOL_DNS_CACHE_TTL = int(os.environ.get("POOL_DNS_CACHE_TTL", "60"))

# TCP keepalive timeout (connection health)
POOL_TCP_KEEPALIVE = int(os.environ.get("POOL_TCP_KEEPALIVE", "60"))

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
# Cache Configuration (Tiered TTL)
# ---------------------------------------------------------------------------

# Local LRU cache size for hot data
CACHE_LOCAL_SIZE = int(os.environ.get("CACHE_LOCAL_SIZE", "1000"))

# Default TTL for cache entries (fallback)
CACHE_DEFAULT_TTL = int(os.environ.get("CACHE_DEFAULT_TTL", "300"))

# Tiered TTL by data type
CACHE_TTL_SENSOR = int(os.environ.get("CACHE_TTL_SENSOR", "60"))      # High-frequency sensor data
CACHE_TTL_RAG = int(os.environ.get("CACHE_TTL_RAG", "600"))          # RAG search results
CACHE_TTL_API = int(os.environ.get("CACHE_TTL_API", "300"))          # API responses
CACHE_TTL_CONFIG = int(os.environ.get("CACHE_TTL_CONFIG", "3600"))   # Config/metadata

# ---------------------------------------------------------------------------
# Pool Configuration Dictionary (for easy passing)
# ---------------------------------------------------------------------------

POOL_CONFIG = {
    "max_connections": POOL_MAX_CONNECTIONS,
    "max_connections_per_host": POOL_MAX_CONNECTIONS_PER_HOST,
    "timeout": POOL_TIMEOUT,
    "health_check_interval": POOL_HEALTH_CHECK_INTERVAL,
    "connector_ttl": POOL_CONNECTOR_TTL,
    "dns_cache_ttl": POOL_DNS_CACHE_TTL,
    "tcp_keepalive": POOL_TCP_KEEPALIVE,
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

CACHE_CONFIG = {
    "local_size": CACHE_LOCAL_SIZE,
    "default_ttl": CACHE_DEFAULT_TTL,
    "ttl_sensor": CACHE_TTL_SENSOR,
    "ttl_rag": CACHE_TTL_RAG,
    "ttl_api": CACHE_TTL_API,
    "ttl_config": CACHE_TTL_CONFIG,
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


def get_cache_config() -> dict:
    """Return cache configuration with tiered TTL."""
    return CACHE_CONFIG.copy()
