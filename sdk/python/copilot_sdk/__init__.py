"""
PilotSuite Core TypeScript SDK

Client SDK for interacting with the PilotSuite Core API.
"""

import os
import requests
from typing import Optional, Dict, Any, List

__version__ = "1.0.0-rc2"
__api_version__ = "v1"


class CoPilotClient:
    """Client for PilotSuite Core API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize the client.
        
        Args:
            base_url: Base URL of the API (default: from env or Home Assistant)
            auth_token: Authentication token (optional)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.environ.get(
            "COPILOT_API_URL", "http://homeassistant.local:8123/api/copilot"
        )
        self.auth_token = auth_token or os.environ.get("COPILOT_AUTH_TOKEN")
        self.timeout = timeout
        self.session = requests.Session()
        if self.auth_token:
            self.session.headers.update({"X-Auth-Token": self.auth_token})

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request."""
        url = f"{self.base_url}/{endpoint}"
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status."""
        return self._request("GET", f"{__api_version__}/system/health")

    def get_mood_context(self) -> Dict[str, Any]:
        """Get current mood context."""
        return self._request("GET", f"{__api_version__}/mood/context")

    def get_brain_graph(self) -> Dict[str, Any]:
        """Get brain graph visualization data."""
        return self._request("GET", f"{__api_version__}/graph/visualization")

    def submit_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit an event to the API.
        
        Args:
            event_type: Type of event (e.g., "user_action", "sensor_update")
            payload: Event data
            
        Returns:
            API response with event_id
        """
        return self._request(
            "POST",
            f"{__api_version__}/events",
            json={"type": event_type, "payload": payload},
        )

    def get_habitus_rules(self) -> List[Dict[str, Any]]:
        """Get discovered Habitus rules (A→B patterns)."""
        return self._request("GET", f"{__api_version__}/habitus/rules")

    def get_tag_registry(self) -> Dict[str, Any]:
        """Get tag registry with entity classifications."""
        return self._request("GET", f"{__api_version__}/tags/registry")

    # ==================== User Preference API ====================

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get all preferences for a user.
        
        Args:
            user_id: User ID (person entity_id)
            
        Returns:
            Dict with user_id and preferences
        """
        return self._request("GET", f"{__api_version__}/user/{user_id}/preferences")

    def get_user_zone_preference(self, user_id: str, zone_id: str) -> Dict[str, Any]:
        """Get preference for a user in a specific zone.
        
        Args:
            user_id: User ID (person entity_id)
            zone_id: Zone ID (e.g., "living", "bedroom")
            
        Returns:
            Dict with user_id, zone_id, and preference
        """
        return self._request("GET", f"{__api_version__}/user/{user_id}/zone/{zone_id}/preference")

    def update_user_preference(
        self,
        user_id: str,
        zone_id: str,
        comfort_bias: Optional[float] = None,
        frugality_bias: Optional[float] = None,
        joy_bias: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update a user's preference for a zone.
        
        Args:
            user_id: User ID (person entity_id)
            zone_id: Zone ID (e.g., "living", "bedroom")
            comfort_bias: Comfort bias (0.0-1.0)
            frugality_bias: Frugality bias (0.0-1.0)
            joy_bias: Joy bias (0.0-1.0)
            
        Returns:
            Updated preference dict
        """
        payload = {"zone_id": zone_id}
        if comfort_bias is not None:
            payload["comfort_bias"] = comfort_bias
        if frugality_bias is not None:
            payload["frugality_bias"] = frugality_bias
        if joy_bias is not None:
            payload["joy_bias"] = joy_bias
            
        return self._request("POST", f"{__api_version__}/user/{user_id}/preference", json=payload)

    def get_active_users(self) -> List[Dict[str, Any]]:
        """Get list of currently active (home) users.
        
        Returns:
            List of active user dicts
        """
        return self._request("GET", f"{__api_version__}/users/active")

    def get_aggregated_mood(self, user_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get aggregated mood for multiple users.
        
        Args:
            user_ids: Optional list of user IDs (default: active users)
            
        Returns:
            Aggregated mood dict with comfort, frugality, joy
        """
        params = {}
        if user_ids:
            params["users"] = ",".join(user_ids)
        return self._request("GET", f"{__api_version__}/mood/aggregated", params=params)

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def get_client(
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> CoPilotClient:
    """Get a configured client instance.
    
    Convenience function for quick client creation.
    """
    return CoPilotClient(base_url=base_url, auth_token=auth_token)
