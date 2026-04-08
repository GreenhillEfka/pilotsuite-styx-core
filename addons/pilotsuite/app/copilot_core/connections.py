"""
Connection Management Module for PilotSuite Core

Provides reusable connections for:
- HA-Supervisor API calls
- Ollama API calls

This module wraps the connection_pool module and provides:
- High-level connection management API
- Connection status tracking
- Graceful reconnection logic
- Backward compatibility layer

Usage:
    from copilot_core.connections import get_ha_connection, get_ollama_connection

    # Get HA connection
    async with get_ha_connection() as conn:
        result = await conn.get("/api/states")

    # Get Ollama connection
    async with get_ollama_connection() as conn:
        result = await conn.generate(model="llama2", prompt="Hello")

Author: Clawdya
Version: 1.0.0
Date: 2026-03-02
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

from .connection_pool import (
    ConnectionPoolManager,
    get_pool_manager,
    get_ha_session,
    get_ollama_session,
    close_pool,
    get_pool_metrics,
)

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Configuration for connections."""
    
    # HA-Supervisor
    ha_base_url: str = field(default="http://homeassistant:8123")
    ha_access_token: str = field(default="")
    ha_timeout: float = field(default=30.0)
    ha_verify_ssl: bool = field(default=True)
    
    # Ollama
    ollama_base_url: str = field(default="http://ollama:11434")
    ollama_timeout: float = field(default=60.0)
    
    # Pool settings
    max_connections: int = field(default=10)
    health_check_interval: int = field(default=60)


@dataclass
class ConnectionStatus:
    """Status of a connection."""
    
    connected: bool = False
    base_url: str = ""
    last_error: Optional[str] = None
    last_success: Optional[float] = None
    response_time_ms: Optional[float] = None
    pool_size: int = 0
    connections_reused: int = 0
    reuse_rate_pct: float = 0.0


class HAConnection:
    """High-level HA-Supervisor connection wrapper."""
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._status = ConnectionStatus()
    
    async def connect(self) -> None:
        """Establish connection to HA-Supervisor."""
        import time
        
        pool = await get_pool_manager()
        self._session = await pool.get_ha_session()
        
        # Test connection
        start = time.monotonic()
        try:
            async with self._session.get(
                f"{self.config.ha_base_url}/api/",
                headers={
                    "Authorization": f"Bearer {self.config.ha_access_token}",
                    "X-Auth-Token": self.config.ha_access_token,
                }
            ) as resp:
                elapsed_ms = (time.monotonic() - start) * 1000
                
                if resp.status == 200:
                    self._status = ConnectionStatus(
                        connected=True,
                        base_url=self.config.ha_base_url,
                        last_success=time.time(),
                        response_time_ms=elapsed_ms,
                    )
                    logger.info(f"HA connection established: {elapsed_ms:.2f}ms")
                else:
                    self._status = ConnectionStatus(
                        connected=False,
                        base_url=self.config.ha_base_url,
                        last_error=f"HTTP {resp.status}",
                    )
        except Exception as e:
            self._status = ConnectionStatus(
                connected=False,
                base_url=self.config.ha_base_url,
                last_error=str(e),
            )
            logger.warning(f"HA connection failed: {e}")
    
    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make GET request to HA-Supervisor."""
        if not self._session:
            await self.connect()
        
        url = f"{self.config.ha_base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {self.config.ha_access_token}",
            "X-Auth-Token": self.config.ha_access_token,
        })
        
        async with self._session.get(url, headers=headers, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def post(self, endpoint: str, data: Optional[dict[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
        """Make POST request to HA-Supervisor."""
        if not self._session:
            await self.connect()
        
        url = f"{self.config.ha_base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {self.config.ha_access_token}",
            "X-Auth-Token": self.config.ha_access_token,
        })
        
        async with self._session.post(url, json=data, headers=headers, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    @property
    def status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self._status
    
    async def close(self) -> None:
        """Close connection (session stays in pool)."""
        self._status.connected = False
        logger.debug("HA connection closed")


class OllamaConnection:
    """High-level Ollama connection wrapper."""
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._status = ConnectionStatus()
    
    async def connect(self) -> None:
        """Establish connection to Ollama."""
        import time
        
        pool = await get_pool_manager()
        self._session = await pool.get_ollama_session()
        
        # Test connection
        start = time.monotonic()
        try:
            async with self._session.get(
                f"{self.config.ollama_base_url}/api/tags"
            ) as resp:
                elapsed_ms = (time.monotonic() - start) * 1000
                
                if resp.status == 200:
                    self._status = ConnectionStatus(
                        connected=True,
                        base_url=self.config.ollama_base_url,
                        last_success=time.time(),
                        response_time_ms=elapsed_ms,
                    )
                    logger.info(f"Ollama connection established: {elapsed_ms:.2f}ms")
                else:
                    self._status = ConnectionStatus(
                        connected=False,
                        base_url=self.config.ollama_base_url,
                        last_error=f"HTTP {resp.status}",
                    )
        except Exception as e:
            self._status = ConnectionStatus(
                connected=False,
                base_url=self.config.ollama_base_url,
                last_error=str(e),
            )
            logger.warning(f"Ollama connection failed: {e}")
    
    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Generate text using Ollama."""
        if not self._session:
            await self.connect()
        
        url = f"{self.config.ollama_base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            **kwargs
        }
        
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        stream: bool = False,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Chat with Ollama."""
        if not self._session:
            await self.connect()
        
        url = f"{self.config.ollama_base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def list_models(self) -> list[dict[str, Any]]:
        """List available Ollama models."""
        if not self._session:
            await self.connect()
        
        url = f"{self.config.ollama_base_url}/api/tags"
        
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("models", [])
    
    @property
    def status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self._status
    
    async def close(self) -> None:
        """Close connection (session stays in pool)."""
        self._status.connected = False
        logger.debug("Ollama connection closed")


# Global connection instances (lazy-initialized)
_ha_connection: Optional[HAConnection] = None
_ollama_connection: Optional[OllamaConnection] = None
_connection_lock = asyncio.Lock()


async def get_ha_connection(config: Optional[ConnectionConfig] = None) -> HAConnection:
    """Get or create HA-Supervisor connection."""
    global _ha_connection
    
    if _ha_connection is None:
        async with _connection_lock:
            if _ha_connection is None:
                _ha_connection = HAConnection(config)
                await _ha_connection.connect()
    
    return _ha_connection


async def get_ollama_connection(config: Optional[ConnectionConfig] = None) -> OllamaConnection:
    """Get or create Ollama connection."""
    global _ollama_connection
    
    if _ollama_connection is None:
        async with _connection_lock:
            if _ollama_connection is None:
                _ollama_connection = OllamaConnection(config)
                await _ollama_connection.connect()
    
    return _ollama_connection


async def close_all_connections() -> None:
    """Close all connections and pool."""
    global _ha_connection, _ollama_connection
    
    if _ha_connection:
        await _ha_connection.close()
        _ha_connection = None
    
    if _ollama_connection:
        await _ollama_connection.close()
        _ollama_connection = None
    
    await close_pool()
    logger.info("All connections closed")


def get_connection_metrics() -> dict[str, Any]:
    """Get connection pool metrics."""
    pool_metrics = get_pool_metrics()
    
    metrics = {
        "ha_connection": {
            "connected": _ha_connection is not None and _ha_connection.status.connected,
            "base_url": _ha_connection.status.base_url if _ha_connection else None,
            "last_error": _ha_connection.status.last_error if _ha_connection else None,
        } if _ha_connection else {"connected": False},
        "ollama_connection": {
            "connected": _ollama_connection is not None and _ollama_connection.status.connected,
            "base_url": _ollama_connection.status.base_url if _ollama_connection else None,
            "last_error": _ollama_connection.status.last_error if _ollama_connection else None,
        } if _ollama_connection else {"connected": False},
        "pool": pool_metrics,
    }
    
    return metrics


# Context managers for easy usage
from contextlib import asynccontextmanager


@asynccontextmanager
async def ha_connection(config: Optional[ConnectionConfig] = None):
    """Context manager for HA-Supervisor connection."""
    conn = await get_ha_connection(config)
    try:
        yield conn
    finally:
        pass  # Connection stays in pool


@asynccontextmanager
async def ollama_connection(config: Optional[ConnectionConfig] = None):
    """Context manager for Ollama connection."""
    conn = await get_ollama_connection(config)
    try:
        yield conn
    finally:
        pass  # Connection stays in pool
