"""PilotSuite Core Python SDK bridge for local tests."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

__version__ = "0.5.1"
__api_version__ = "v1"


class CoPilotClient:
    """Client for PilotSuite Core API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 30,
    ):
        self.base_url = base_url or os.environ.get(
            "COPILOT_API_URL", "http://homeassistant.local:8123/api/copilot"
        )
        self.auth_token = auth_token or os.environ.get("COPILOT_AUTH_TOKEN")
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self):
        session = requests.Session()
        if self.auth_token:
            session.headers.update({"X-Auth-Token": self.auth_token})
        return session

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        self.session = self._create_session()
        url = f"{self.base_url}/{endpoint}"
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_system_health(self) -> Dict[str, Any]:
        return self._request("GET", f"{__api_version__}/system/health")

    def get_mood_context(self) -> Dict[str, Any]:
        return self._request("GET", f"{__api_version__}/mood/context")

    def get_brain_graph(self) -> Dict[str, Any]:
        return self._request("GET", f"{__api_version__}/graph/visualization")

    def submit_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"{__api_version__}/events",
            json={"type": event_type, "payload": payload},
        )

    def get_habitus_rules(self) -> List[Dict[str, Any]]:
        return self._request("GET", f"{__api_version__}/habitus/rules")

    def get_tag_registry(self) -> Dict[str, Any]:
        return self._request("GET", f"{__api_version__}/tags/registry")

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_client(
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> CoPilotClient:
    return CoPilotClient(base_url=base_url, auth_token=auth_token)
