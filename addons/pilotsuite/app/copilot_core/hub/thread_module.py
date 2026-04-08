"""Thread Netzwerkmodul — Thread/Matter Netzwerkstatus-Tracking (v1.0.0).

Verfolgt den Thread Netzwerkzustand ueber HA Entity States:
Border-Router-Status, Geraeteanzahl, Router-Anzahl.

Features:
- Border-Router-Status-Tracking
- Geraetezaehlung mit Router-Erkennung
- Letztes Update-Zeitstempel
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ThreadDevice:
    """Einzelnes Thread Geraet."""

    entity_id: str
    friendly_name: str = ""
    state: str = "unknown"
    is_router: bool = False
    last_seen: datetime | None = None


@dataclass
class ThreadDashboard:
    """Komplettes Thread Netzwerk-Dashboard."""

    border_router_state: str = "unknown"
    device_count: int = 0
    router_count: int = 0
    last_update: datetime | None = None
    devices: list[dict[str, Any]] = field(default_factory=list)


class ThreadModuleEngine:
    """Thread Netzwerkmodul Engine — verwaltet Thread Netzwerkstatus."""

    def __init__(self) -> None:
        self._devices: dict[str, ThreadDevice] = {}
        self._border_router_state: str = "unknown"
        self._last_update: datetime | None = None
        self._config: dict[str, Any] = {
            "enabled": True,
            "polling_interval_s": 120,
        }

    def update_from_ha(self, states: dict[str, Any]) -> None:
        """Verarbeitet HA Entity States fuer Thread Netzwerk.

        Erwartet ein Dict mit entity_id -> state-Objekt (dict mit
        'state', 'attributes', etc.) wie von der HA States API.
        Matched werden Entities mit Prefix ``thread.`` oder
        ``sensor.*thread*``.
        """
        try:
            self._devices.clear()
            now = datetime.now(tz=timezone.utc)
            self._last_update = now

            for entity_id, state_obj in states.items():
                if not isinstance(state_obj, dict):
                    continue

                eid_lower = entity_id.lower()
                if not (eid_lower.startswith("thread.") or
                        (eid_lower.startswith("sensor.") and "thread" in eid_lower)):
                    continue

                try:
                    state_val = str(state_obj.get("state", "unknown"))
                    attrs = state_obj.get("attributes", {}) or {}
                    friendly = str(attrs.get("friendly_name", entity_id))

                    # Border-Router-Entity erkennen
                    if "border_router" in eid_lower or "otbr" in eid_lower:
                        self._border_router_state = state_val
                        continue

                    is_router = (
                        attrs.get("role", "").lower() in ("router", "leader") or
                        "router" in eid_lower
                    )

                    device = ThreadDevice(
                        entity_id=entity_id,
                        friendly_name=friendly,
                        state=state_val,
                        is_router=is_router,
                        last_seen=_parse_datetime(attrs.get("last_seen")),
                    )
                    self._devices[entity_id] = device
                except Exception:
                    logger.debug("Thread Modul: Fehler beim Parsen von %s", entity_id, exc_info=True)
        except Exception:
            logger.warning("Thread Modul: Fehler bei update_from_ha", exc_info=True)

    def get_status(self) -> ThreadDashboard:
        """Erstellt das komplette Thread Netzwerk-Dashboard."""
        devices_data: list[dict[str, Any]] = []
        router_count = 0

        for device in self._devices.values():
            if device.is_router:
                router_count += 1
            devices_data.append({
                "entity_id": device.entity_id,
                "friendly_name": device.friendly_name,
                "state": device.state,
                "is_router": device.is_router,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            })

        return ThreadDashboard(
            border_router_state=self._border_router_state,
            device_count=len(self._devices),
            router_count=router_count,
            last_update=self._last_update,
            devices=devices_data,
        )

    def get_dashboard(self) -> ThreadDashboard:
        """Alias fuer get_status() — Dashboard-Kompatibilitaet."""
        return self.get_status()

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_status()
        return {
            "border_router_state": d.border_router_state,
            "device_count": d.device_count,
            "router_count": d.router_count,
            "last_update": d.last_update.isoformat() if d.last_update else None,
            "devices": d.devices,
        }

    def get_config(self) -> dict[str, Any]:
        """Gibt aktuelle Modul-Konfiguration zurueck."""
        return dict(self._config)

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Aktualisiert Modul-Konfiguration."""
        self._config.update(updates)
        return dict(self._config)

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_status()
        if d.device_count == 0 and d.border_router_state == "unknown":
            return ""
        lines = [
            f"Thread Netzwerk: Border Router {d.border_router_state}, "
            f"{d.device_count} Geraete, {d.router_count} Router"
        ]
        if d.last_update:
            lines.append(f"  Letztes Update: {d.last_update.isoformat()}")
        for dev in d.devices:
            if dev["state"] in ("unavailable", "offline"):
                lines.append(
                    f"  WARNUNG: {dev['friendly_name']} ist {dev['state']} ({dev['entity_id']})"
                )
        return "\n".join(lines)


def _parse_datetime(value: Any) -> datetime | None:
    """Versucht einen Datetime-String zu parsen."""
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
