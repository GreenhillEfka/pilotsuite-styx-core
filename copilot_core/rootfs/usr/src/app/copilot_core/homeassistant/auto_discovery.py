"""HomeAssistant Auto-Discovery.

Handles automatic discovery of HomeAssistant instances via:
- Configured URL
- mDNS/DNS-SD (homeassistant.local)
- Network scan fallback
"""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from typing import Any, Optional

from .client import HomeAssistantClient, HAConnectionConfig, HAConnectionStatus

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredInstance:
    """Discovered HomeAssistant instance."""
    
    base_url: str
    friendly_name: str = ""
    version: str = ""
    response_time_ms: float = 0.0
    requires_auth: bool = True


class AutoDiscovery:
    """Auto-discovery for HomeAssistant instances."""
    
    DEFAULT_HOSTNAMES = [
        "homeassistant.local",
        "homeassistant",
        "hass.local",
        "hass",
    ]
    
    DEFAULT_PORTS = [8123, 8124]
    
    def __init__(self):
        self._discovered: list[DiscoveredInstance] = []
        self._active_client: Optional[HomeAssistantClient] = None
    
    async def discover(
        self,
        configured_url: Optional[str] = None,
        timeout_seconds: float = 5.0
    ) -> list[DiscoveredInstance]:
        """Discover HomeAssistant instances.
        
        Priority:
        1. Configured URL (if provided)
        2. mDNS/DNS-SD resolution
        3. Default hostnames
        """
        self._discovered = []
        candidates = []
        
        # 1. Add configured URL
        if configured_url:
            candidates.append(configured_url)
        
        # 2. Try mDNS resolution
        mdns_urls = await self._resolve_mdns()
        candidates.extend(mdns_urls)
        
        # 3. Add default hostnames
        for hostname in self.DEFAULT_HOSTNAMES:
            for port in self.DEFAULT_PORTS:
                candidates.append(f"http://{hostname}:{port}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for url in candidates:
            if url not in seen:
                seen.add(url)
                unique_candidates.append(url)
        
        logger.info(f"Discovering HA instances: {len(unique_candidates)} candidates")
        
        # Test all candidates concurrently
        tasks = [
            self._test_candidate(url, timeout_seconds)
            for url in unique_candidates
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, DiscoveredInstance):
                self._discovered.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Discovery task failed: {result}")
        
        # Sort by response time (fastest first)
        self._discovered.sort(key=lambda x: x.response_time_ms)
        
        logger.info(f"Discovered {len(self._discovered)} HA instance(s)")
        
        return self._discovered
    
    async def _resolve_mdns(self) -> list[str]:
        """Resolve homeassistant.local via DNS/mDNS."""
        urls = []
        
        for hostname in self.DEFAULT_HOSTNAMES:
            try:
                # Try to resolve hostname
                ip = await asyncio.get_running_loop().run_in_executor(
                    None,
                    self._resolve_host,
                    hostname
                )
                
                if ip:
                    for port in self.DEFAULT_PORTS:
                        urls.append(f"http://{hostname}:{port}")
                    logger.debug(f"Resolved {hostname} to {ip}")
            
            except Exception as e:
                logger.debug(f"Failed to resolve {hostname}: {e}")
        
        return urls
    
    def _resolve_host(self, hostname: str) -> Optional[str]:
        """Resolve hostname to IP (blocking, run in executor)."""
        try:
            result = socket.gethostbyname(hostname)
            return result
        except socket.gaierror:
            return None
    
    async def _test_candidate(
        self,
        url: str,
        timeout_seconds: float
    ) -> Optional[DiscoveredInstance]:
        """Test a candidate URL."""
        config = HAConnectionConfig(
            base_url=url,
            access_token="",  # No token for discovery
            timeout_seconds=timeout_seconds,
            verify_ssl=False,  # Allow self-signed during discovery
            retry_count=1,  # No retries during discovery
        )
        
        client = HomeAssistantClient(config)
        
        try:
            status = await client.test_connection()
            
            if status.connected:
                # Try to get instance info
                friendly_name = ""
                version = ""
                
                try:
                    info = await client.get("/api/config")
                    friendly_name = info.get("name", "")
                    version = info.get("version", "")
                except Exception as exc:
                    logger.debug("Failed to get HA config from %s: %s", url, exc)

                await client.close()
                
                return DiscoveredInstance(
                    base_url=url,
                    friendly_name=friendly_name,
                    version=version,
                    response_time_ms=status.response_time_ms or 0.0,
                    requires_auth=True
                )
        
        except Exception as e:
            logger.debug(f"Candidate {url} failed: {e}")
        
        finally:
            await client.close()
        
        return None
    
    async def connect(
        self,
        base_url: str,
        access_token: str,
        verify_ssl: bool = True,
        timeout_seconds: float = 5.0
    ) -> HomeAssistantClient:
        """Connect to a specific HomeAssistant instance."""
        config = HAConnectionConfig(
            base_url=base_url,
            access_token=access_token,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
        )
        
        client = HomeAssistantClient(config)
        status = await client.test_connection()
        
        if not status.connected:
            await client.close()
            raise ConnectionError(
                f"Failed to connect to {base_url}: {status.last_error}"
            )
        
        self._active_client = client
        logger.info(f"Connected to HA at {base_url}")
        
        return client
    
    async def get_active_client(self) -> Optional[HomeAssistantClient]:
        """Get the currently active client."""
        return self._active_client
    
    def get_discovered(self) -> list[DiscoveredInstance]:
        """Get list of discovered instances."""
        return self._discovered
    
    async def close(self) -> None:
        """Close active client."""
        if self._active_client:
            await self._active_client.close()
            self._active_client = None
