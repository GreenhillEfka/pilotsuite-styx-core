"""Factory for creating Home Assistant Bridge v2 adapter instances - Slice 311"""

from __future__ import annotations
from typing import Dict, Any
import logging

from .adapter import HABridgeV2Adapter
from .config import HABridgeV2Config
from .interface import HABridgeV2Interface

_LOGGER = logging.getLogger(__name__)


class HABridgeV2AdapterFactory:
    """Factory for creating Home Assistant Bridge v2 adapter instances"""
    
    @staticmethod
    def create_from_config(config_dict: Dict[str, Any] = None) -> HABridgeV2Interface:
        """Create an adapter instance from configuration
        
        Args:
            config_dict: Optional configuration dictionary
            
        Returns:
            HABridgeV2Interface: Configured adapter instance
        """
        try:
            config = HABridgeV2Config(config_dict)
            
            if config.enable_debug_logging:
                logging.getLogger("homeassistant_bridge_v2").setLevel(logging.DEBUG)
            
            adapter = HABridgeV2Adapter(
                ha_url=config.ha_url,
                ha_token=config.ha_token
            )
            
            _LOGGER.info("Created Home Assistant Bridge v2 adapter")
            return adapter
            
        except Exception as e:
            _LOGGER.error(f"Failed to create HA Bridge v2 adapter: {e}")
            raise
            
    @staticmethod
    def create_from_env() -> HABridgeV2Interface:
        """Create an adapter instance from environment variables
        
        Returns:
            HABridgeV2Interface: Configured adapter instance
        """
        return HABridgeV2AdapterFactory.create_from_config()