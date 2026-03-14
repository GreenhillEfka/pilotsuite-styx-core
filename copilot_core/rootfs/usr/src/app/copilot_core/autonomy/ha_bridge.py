"""HA Service Call Bridge — Direct HA service calls from Core.

Uses SUPERVISOR_API + SUPERVISOR_TOKEN (same pattern as onyx_bridge.py)
with Circuit Breaker protection against cascading failures.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import requests

from copilot_core.circuit_breaker import CircuitOpenError, ha_supervisor_breaker

_LOGGER = logging.getLogger(__name__)

SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


@dataclass
class ServiceCallResult:
    """Result of an HA service call."""

    ok: bool
    domain: str = ""
    service: str = ""
    entity_ids: List[str] = field(default_factory=list)
    ha_status_code: int = 0
    error: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HABridge:
    """Bridge for calling HA services from Core.

    Uses the Supervisor API with circuit breaker protection.
    """

    def __init__(
        self,
        supervisor_api: str | None = None,
        supervisor_token: str | None = None,
        timeout: int = 10,
    ) -> None:
        self._api = supervisor_api or SUPERVISOR_API
        self._token = supervisor_token or SUPERVISOR_TOKEN
        self._timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ── Generic service call ────────────────────────────────────────────

    def call_service(
        self,
        domain: str,
        service: str,
        service_data: Dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> ServiceCallResult:
        """Execute an HA service call through the Supervisor API.

        Args:
            domain: HA domain (e.g. "light", "media_player").
            service: Service name (e.g. "turn_on").
            service_data: Service data dict.
            timeout: Request timeout override.

        Returns:
            ServiceCallResult with ok/error details.
        """
        if not self._token:
            return ServiceCallResult(
                ok=False, domain=domain, service=service,
                error="No SUPERVISOR_TOKEN configured",
            )

        url = f"{self._api}/services/{domain}/{service}"
        payload = service_data or {}
        entity_ids = []
        if "entity_id" in payload:
            eid = payload["entity_id"]
            entity_ids = [eid] if isinstance(eid, str) else list(eid)

        try:
            def _do_call():
                return requests.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=timeout or self._timeout,
                )

            resp = ha_supervisor_breaker.call(_do_call)

            return ServiceCallResult(
                ok=resp.status_code < 400,
                domain=domain,
                service=service,
                entity_ids=entity_ids,
                ha_status_code=resp.status_code,
                error="" if resp.status_code < 400 else resp.text[:200],
            )

        except CircuitOpenError:
            _LOGGER.warning("HA circuit breaker open — skipping %s.%s", domain, service)
            return ServiceCallResult(
                ok=False, domain=domain, service=service,
                entity_ids=entity_ids, error="Circuit breaker open",
            )
        except requests.RequestException as exc:
            _LOGGER.warning("HA service call failed: %s.%s → %s", domain, service, exc)
            return ServiceCallResult(
                ok=False, domain=domain, service=service,
                entity_ids=entity_ids, error=str(exc)[:200],
            )

    # ── Convenience methods ─────────────────────────────────────────────

    def turn_on_light(
        self,
        entity_id: str,
        brightness_pct: int = 100,
        color_temp_k: int | None = None,
    ) -> ServiceCallResult:
        """Turn on a light with brightness and optional color temperature."""
        data: Dict[str, Any] = {
            "entity_id": entity_id,
            "brightness_pct": max(0, min(100, brightness_pct)),
        }
        if color_temp_k and color_temp_k > 0:
            # HA uses kelvin directly
            data["color_temp_kelvin"] = color_temp_k
        return self.call_service("light", "turn_on", data)

    def turn_off_light(self, entity_id: str) -> ServiceCallResult:
        """Turn off a light."""
        return self.call_service("light", "turn_off", {"entity_id": entity_id})

    def get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get the current state of an entity from HA.

        Returns:
            State dict or None on error.
        """
        if not self._token:
            return None

        url = f"{self._api}/states/{entity_id}"

        try:
            def _do():
                return requests.get(
                    url, headers=self._headers(), timeout=self._timeout,
                )

            resp = ha_supervisor_breaker.call(_do)
            if resp.status_code == 200:
                return resp.json()
            return None

        except (CircuitOpenError, requests.RequestException):
            return None
