"""Zigbee Netzwerkmodul — Zigbee Netzwerkstatus-Tracking (v1.0.0).

Verfolgt den Zigbee Netzwerkzustand ueber HA Entity States:
Coordinator-Status, Geraeteanzahl, LQI-Statistiken, Offline-Geraete.

Features:
- Coordinator-Status-Tracking
- Geraetezaehlung mit Offline-Erkennung
- LQI-Statistiken (Durchschnitt ueber alle Geraete)
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
class ZigbeeDevice:
    """Einzelnes Zigbee Geraet."""

    entity_id: str
    friendly_name: str = ""
    state: str = "unknown"
    lqi: int | None = None
    is_offline: bool = False
    last_seen: datetime | None = None


@dataclass
class ZigbeeDashboard:
    """Komplettes Zigbee Netzwerk-Dashboard."""

    coordinator_state: str = "unknown"
    device_count: int = 0
    avg_lqi: float = 0.0
    devices_offline: int = 0
    last_update: datetime | None = None
    devices: list[dict[str, Any]] = field(default_factory=list)


class ZigbeeModuleEngine:
    """Zigbee Netzwerkmodul Engine — verwaltet Zigbee Netzwerkstatus."""

    def __init__(self) -> None:
        self._devices: dict[str, ZigbeeDevice] = {}
        self._coordinator_state: str = "unknown"
        self._last_update: datetime | None = None

    def update_from_ha(self, states: dict[str, Any]) -> None:
        """Verarbeitet HA Entity States fuer Zigbee Netzwerk.

        Erwartet ein Dict mit entity_id -> state-Objekt (dict mit
        'state', 'attributes', etc.) wie von der HA States API.
        Matched werden Entities mit ``sensor.*zigbee*`` oder
        Prefix ``zha.*``.
        """
        try:
            self._devices.clear()
            now = datetime.now(tz=timezone.utc)
            self._last_update = now

            for entity_id, state_obj in states.items():
                if not isinstance(state_obj, dict):
                    continue

                eid_lower = entity_id.lower()
                if not ((eid_lower.startswith("sensor.") and "zigbee" in eid_lower) or
                        eid_lower.startswith("zha.")):
                    continue

                try:
                    state_val = str(state_obj.get("state", "unknown"))
                    attrs = state_obj.get("attributes", {}) or {}
                    friendly = str(attrs.get("friendly_name", entity_id))

                    # Coordinator-Entity erkennen
                    if "coordinator" in eid_lower or "gateway" in eid_lower:
                        self._coordinator_state = state_val
                        continue

                    lqi = _safe_int_or_none(attrs.get("lqi"))
                    is_offline = state_val in ("unavailable", "offline", "unknown")

                    device = ZigbeeDevice(
                        entity_id=entity_id,
                        friendly_name=friendly,
                        state=state_val,
                        lqi=lqi,
                        is_offline=is_offline,
                        last_seen=_parse_datetime(attrs.get("last_seen")),
                    )
                    self._devices[entity_id] = device
                except Exception:
                    logger.debug("Zigbee Modul: Fehler beim Parsen von %s", entity_id, exc_info=True)
        except Exception:
            logger.warning("Zigbee Modul: Fehler bei update_from_ha", exc_info=True)

    def get_status(self) -> ZigbeeDashboard:
        """Erstellt das komplette Zigbee Netzwerk-Dashboard."""
        devices_data: list[dict[str, Any]] = []
        offline_count = 0
        lqi_values: list[int] = []

        for device in self._devices.values():
            if device.is_offline:
                offline_count += 1
            if device.lqi is not None:
                lqi_values.append(device.lqi)
            devices_data.append({
                "entity_id": device.entity_id,
                "friendly_name": device.friendly_name,
                "state": device.state,
                "lqi": device.lqi,
                "is_offline": device.is_offline,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            })

        avg_lqi = round(sum(lqi_values) / len(lqi_values), 1) if lqi_values else 0.0

        return ZigbeeDashboard(
            coordinator_state=self._coordinator_state,
            device_count=len(self._devices),
            avg_lqi=avg_lqi,
            devices_offline=offline_count,
            last_update=self._last_update,
            devices=devices_data,
        )

    def get_dashboard(self) -> ZigbeeDashboard:
        """Alias fuer get_status() — Dashboard-Kompatibilitaet."""
        return self.get_status()

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_status()
        return {
            "coordinator_state": d.coordinator_state,
            "device_count": d.device_count,
            "avg_lqi": d.avg_lqi,
            "devices_offline": d.devices_offline,
            "last_update": d.last_update.isoformat() if d.last_update else None,
            "devices": d.devices,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_status()
        if d.device_count == 0 and d.coordinator_state == "unknown":
            return ""
        lines = [
            f"Zigbee Netzwerk: Coordinator {d.coordinator_state}, "
            f"{d.device_count} Geraete, {d.devices_offline} offline, "
            f"LQI Durchschnitt {d.avg_lqi}"
        ]
        for dev in d.devices:
            if dev["is_offline"]:
                lines.append(f"  WARNUNG: {dev['friendly_name']} ist offline ({dev['entity_id']})")
            elif dev["lqi"] is not None and dev["lqi"] < 50:
                lines.append(
                    f"  Schwaches Signal: {dev['friendly_name']} LQI={dev['lqi']} ({dev['entity_id']})"
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


def _safe_int_or_none(value: Any) -> int | None:
    """Sichere Integer-Konvertierung, gibt None bei Fehler zurueck."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
