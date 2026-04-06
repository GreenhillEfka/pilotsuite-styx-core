"""Configuration for Home Assistant Bridge v2 - Slice 311"""

from __future__ import annotations
from typing import Dict, Any
import os


class HABridgeV2Config:
    """Configuration class for Home Assistant Bridge v2 adapter"""
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        """Initialize configuration with optional dictionary override"""
        if config_dict:
            self._config = config_dict
        else:
            self._config = {
                "ha_url": os.getenv("HA_URL", "http://localhost:8123"),
                "ha_token": os.getenv("HA_TOKEN", ""),
                "sync_interval": int(os.getenv("HA_SYNC_INTERVAL", "300")),  # 5 minutes
                "enable_debug_logging": os.getenv("HA_DEBUG_LOGGING", "false").lower() == "true"
            }
    
    @property
    def ha_url(self) -> str:
        """Home Assistant URL"""
        return self._config.get("ha_url")
        
    @property
    def ha_token(self) -> str:
        """Home Assistant Long-Lived Access Token"""
        return self._config.get("ha_token")
        
    @property
    def sync_interval(self) -> int:
        """Interval in seconds between permission sync operations"""
        return self._config.get("sync_interval")
        
    @property
    def enable_debug_logging(self) -> bool:
        """Whether to enable debug logging"""
        return self._config.get("enable_debug_logging")
        
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary"""
        return self._config.copy()