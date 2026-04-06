"""Home Assistant Bridge v2 Interface Definition - Slice 311"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any


class HABridgeV2Interface(ABC):
    """Abstract interface for Home Assistant Bridge v2 integration"""
    
    @abstractmethod
    def sync_permissions_to_ha(self) -> bool:
        """Sync permissions from Core API to Home Assistant
        
        Returns:
            bool: True if sync was successful, False otherwise
        """
        pass
        
    @abstractmethod
    def handle_ha_permission_request(self, permission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle permission requests coming from Home Assistant
        
        Args:
            permission_data: Dictionary containing permission creation data
            
        Returns:
            Dictionary with success status and result/error information
        """
        pass
        
    @abstractmethod
    def handle_ha_permission_delete(self, permission_id: str) -> Dict[str, Any]:
        """Handle permission deletion requests from Home Assistant
        
        Args:
            permission_id: ID of the permission to delete
            
        Returns:
            Dictionary with success status and result/error information
        """
        pass
        
    @abstractmethod
    def get_ha_permission_info(self, permission_id: str) -> Dict[str, Any]:
        """Get detailed permission information from both systems
        
        Args:
            permission_id: ID of the permission to retrieve information for
            
        Returns:
            Dictionary with success status and combined information from both systems
        """
        pass