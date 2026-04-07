"""
Connection Pool Manager for PilotSuite Core

Provides aiohttp.ClientSession pooling for:
- HA-Supervisor API calls
- Ollama API calls

Features:
- Configurable pool size (default: 10 connections per target)
- Connection reuse instead of new connection per request
- Timeout handling per connection
- Health-check for pool connections
- Automatic cleanup on shutdown

Usage:
    from copilot_core.connection_pool import get_ha_session, get_ollama_session

    async with get_ha_session() as session:
        async with session.get(url) as resp:
            ...

    async with get_ollama_session() as session:
        async with session.post(url, json=data) as resp:
            ...
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Pool configuration from environment
DEFAULT_MAX_CONNECTIONS = int(os.environ.get("POOL_MAX_CONNECTIONS", "25"))
DEFAULT_MAX_CONNECTIONS_PER_HOST = int(os.environ.get("POOL_MAX_CONNECTIONS_PER_HOST", "5"))
DEFAULT_CONNECTION_TIMEOUT = int(os.environ.get("POOL_TIMEOUT", "30"))
DEFAULT_HEALTH_CHECK_INTERVAL = int(os.environ.get("POOL_HEALTH_CHECK_INTERVAL", "60"))

# Connector limits
CONNECTOR_LIMIT = DEFAULT_MAX_CONNECTIONS
CONNECTOR_LIMIT_PER_HOST = DEFAULT_MAX_CONNECTIONS_PER_HOST
CONNECTOR_TTL = int(os.environ.get("POOL_CONNECTOR_TTL", "180"))  # seconds before connection recycling
CONNECTOR_DNS_CACHE_TTL = int(os.environ.get("POOL_DNS_CACHE_TTL", "60"))
CONNECTOR_TCP_KEEPALIVE = int(os.environ.get("POOL_TCP_KEEPALIVE", "60"))


class ConnectionPoolManager:
    """Manages aiohttp.ClientSession pools for different targets."""

    def __init__(
        self,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        timeout: int = DEFAULT_CONNECTION_TIMEOUT,
        health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
    ):
        self.max_connections = max_connections
        self.timeout = timeout
        self.health_check_interval = health_check_interval

        self._ha_connector: Optional[aiohttp.TCPConnector] = None
        self._ha_session: Optional[aiohttp.ClientSession] = None
        self._ollama_connector: Optional[aiohttp.TCPConnector] = None
        self._ollama_session: Optional[aiohttp.ClientSession] = None

        self._ha_last_health_check = 0.0
        self._ollama_last_health_check = 0.0
        self._ha_health_status = True
        self._ollama_health_status = True

        self._lock = asyncio.Lock()
        self._closed = False

        # Metrics
        self._ha_requests_total = 0
        self._ollama_requests_total = 0
        self._ha_connections_reused = 0
        self._ollama_connections_reused = 0

    async def _create_connector(self) -> aiohttp.TCPConnector:
        """Create a TCP connector with pooling settings."""
        return aiohttp.TCPConnector(
            limit=CONNECTOR_LIMIT,
            limit_per_host=CONNECTOR_LIMIT_PER_HOST,
            ttl_dns_cache=CONNECTOR_DNS_CACHE_TTL,
            use_dns_cache=True,
            enable_cleanup_closed=True,
            keepalive_timeout=CONNECTOR_TCP_KEEPALIVE,
        )

    async def _create_session(
        self, connector: aiohttp.TCPConnector
    ) -> aiohttp.ClientSession:
        """Create a ClientSession with timeout and pooling settings."""
        timeout = aiohttp.ClientTimeout(
            total=self.timeout,
            connect=10,
            sock_read=self.timeout,
            sock_connect=10,
        )
        return aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            trust_env=True,
            headers={"User-Agent": "PilotSuite-Styx-Core/1.0"},
        )

    async def get_ha_session(self) -> aiohttp.ClientSession:
        """Get or create HA-Supervisor session."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("ConnectionPoolManager is closed")

            if self._ha_session is None or self._ha_session.closed:
                self._ha_connector = await self._create_connector()
                self._ha_session = await self._create_session(self._ha_connector)
                logger.info(
                    "Created HA-Supervisor session (pool_size=%d, timeout=%ds)",
                    self.max_connections,
                    self.timeout,
                )
            return self._ha_session

    async def get_ollama_session(self) -> aiohttp.ClientSession:
        """Get or create Ollama session."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("ConnectionPoolManager is closed")

            if self._ollama_session is None or self._ollama_session.closed:
                self._ollama_connector = await self._create_connector()
                self._ollama_session = await self._create_session(
                    self._ollama_connector
                )
                logger.info(
                    "Created Ollama session (pool_size=%d, timeout=%ds)",
                    self.max_connections,
                    self.timeout,
                )
            return self._ollama_session

    async def health_check(self, url: str, session: aiohttp.ClientSession) -> bool:
        """Perform health check on a session."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status < 500
        except Exception:
            return False

    async def check_ha_health(self, ha_url: str) -> bool:
        """Check HA-Supervisor health status."""
        now = time.monotonic()
        if now - self._ha_last_health_check < self.health_check_interval:
            return self._ha_health_status

        self._ha_last_health_check = now
        session = await self.get_ha_session()
        self._ha_health_status = await self.health_check(f"{ha_url}/ready", session)

        if not self._ha_health_status:
            logger.warning("HA-Supervisor health check failed")
        return self._ha_health_status

    async def check_ollama_health(self, ollama_url: str) -> bool:
        """Check Ollama health status."""
        now = time.monotonic()
        if now - self._ollama_last_health_check < self.health_check_interval:
            return self._ollama_health_status

        self._ollama_last_health_check = now
        session = await self.get_ollama_session()
        self._ollama_health_status = await self.health_check(
            f"{ollama_url}/api/tags", session
        )

        if not self._ollama_health_status:
            logger.warning("Ollama health check failed")
        return self._ollama_health_status

    def record_ha_request(self, reused: bool = False):
        """Record HA request metric."""
        self._ha_requests_total += 1
        if reused:
            self._ha_connections_reused += 1

    def record_ollama_request(self, reused: bool = False):
        """Record Ollama request metric."""
        self._ollama_requests_total += 1
        if reused:
            self._ollama_connections_reused += 1

    def get_metrics(self) -> dict:
        """Return pool metrics."""
        ha_reuse_rate = (
            self._ha_connections_reused / max(1, self._ha_requests_total) * 100
        )
        ollama_reuse_rate = (
            self._ollama_connections_reused / max(1, self._ollama_requests_total) * 100
        )

        return {
            "ha_pool": {
                "requests_total": self._ha_requests_total,
                "connections_reused": self._ha_connections_reused,
                "reuse_rate_pct": round(ha_reuse_rate, 1),
                "healthy": self._ha_health_status,
                "session_active": self._ha_session is not None
                and not self._ha_session.closed,
            },
            "ollama_pool": {
                "requests_total": self._ollama_requests_total,
                "connections_reused": self._ollama_connections_reused,
                "reuse_rate_pct": round(ollama_reuse_rate, 1),
                "healthy": self._ollama_health_status,
                "session_active": self._ollama_session is not None
                and not self._ollama_session.closed,
            },
            "config": {
                "max_connections": self.max_connections,
                "timeout": self.timeout,
                "health_check_interval": self.health_check_interval,
            },
        }

    async def close(self):
        """Close all sessions and connectors."""
        async with self._lock:
            self._closed = True

            if self._ha_session and not self._ha_session.closed:
                await self._ha_session.close()
                logger.info("Closed HA-Supervisor session")

            if self._ollama_session and not self._ollama_session.closed:
                await self._ollama_session.close()
                logger.info("Closed Ollama session")

            self._ha_session = None
            self._ollama_session = None
            self._ha_connector = None
            self._ollama_connector = None


# Global pool instance (lazy-initialized)
_pool_manager: Optional[ConnectionPoolManager] = None
_pool_lock = asyncio.Lock()


async def get_pool_manager() -> ConnectionPoolManager:
    """Get or create the global pool manager."""
    global _pool_manager
    if _pool_manager is not None:
        return _pool_manager

    async with _pool_lock:
        if _pool_manager is not None:
            return _pool_manager

        _pool_manager = ConnectionPoolManager()
        logger.info("Initialized global ConnectionPoolManager")
        return _pool_manager


@asynccontextmanager
async def get_ha_session():
    """Context manager for HA-Supervisor session."""
    pool = await get_pool_manager()
    session = await pool.get_ha_session()
    pool.record_ha_request(reused=True)  # Session reuse
    try:
        yield session
    finally:
        pass  # Session stays open for reuse


@asynccontextmanager
async def get_ollama_session():
    """Context manager for Ollama session."""
    pool = await get_pool_manager()
    session = await pool.get_ollama_session()
    pool.record_ollama_request(reused=True)  # Session reuse
    try:
        yield session
    finally:
        pass  # Session stays open for reuse


async def close_pool():
    """Close the global pool manager."""
    global _pool_manager
    if _pool_manager is not None:
        await _pool_manager.close()
        _pool_manager = None
        logger.info("Closed global ConnectionPoolManager")


def get_pool_metrics() -> dict:
    """Get pool metrics (sync wrapper)."""
    if _pool_manager is None:
        return {"error": "Pool not initialized"}
    return _pool_manager.get_metrics()
