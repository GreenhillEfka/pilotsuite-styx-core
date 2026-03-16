"""Z-Wave Netzwerkmodul — Z-Wave Netzwerkstatus-Tracking (v1.0.0).

Verfolgt den Z-Wave Netzwerkzustand ueber HA Entity States:
Controller-Status, Geraeteanzahl, Heal-Status, Fehlerquote.

Features:
- Controller-Status-Tracking (ready, not ready, error)
- Geraetezaehlung mit Status-Klassifizierung (dead, sleeping)
- Heal-Status und letzte Heal-Zeit
- Fehlerzaehlung fuer Netzwerkprobleme
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ZWaveDevice:
    """Einzelnes Z-Wave Geraet."""

    entity_id: str
    friendly_name: str = ""
    state: str = "unknown"
    is_dead: bool = False
    is_sleeping: bool = False
    last_seen: datetime | None = None


@dataclass
class ZWaveDashboard:
    """Komplettes Z-Wave Netzwerk-Dashboard."""

    controller_state: str = "unknown"
    device_count: int = 0
    devices_dead: int = 0
    devices_sleeping: int = 0
    last_heal: datetime | None = None
    error_count: int = 0
    devices: list[dict[str, Any]] = field(default_factory=list)


class ZWaveModuleEngine:
    """Z-Wave Netzwerkmodul Engine — verwaltet Z-Wave Netzwerkstatus."""

    def __init__(self) -> None:
        self._devices: dict[str, ZWaveDevice] = {}
        self._controller_state: str = "unknown"
        self._last_heal: datetime | None = None
        self._error_count: int = 0

    def update_from_ha(self, states: dict[str, Any]) -> None:
        """Verarbeitet HA Entity States fuer Z-Wave Netzwerk.

        Erwartet ein Dict mit entity_id -> state-Objekt (dict mit
        'state', 'attributes', etc.) wie von der HA States API.
        Matched werden Entities mit Prefix ``zwave_js.`` oder
        ``sensor.*zwave*``.
        """
        try:
            self._devices.clear()
            for entity_id, state_obj in states.items():
                if not isinstance(state_obj, dict):
                    continue

                eid_lower = entity_id.lower()
                if not (eid_lower.startswith("zwave_js.") or
                        (eid_lower.startswith("sensor.") and "zwave" in eid_lower)):
                    continue

                try:
                    state_val = str(state_obj.get("state", "unknown"))
                    attrs = state_obj.get("attributes", {}) or {}
                    friendly = str(attrs.get("friendly_name", entity_id))

                    # Controller-Entity erkennen
                    if "controller" in eid_lower or "network" in eid_lower:
                        self._controller_state = state_val
                        if "heal" in eid_lower:
                            self._last_heal = _parse_datetime(attrs.get("last_heal"))
                        if "error" in eid_lower:
                            self._error_count = _safe_int(state_val)
                        continue

                    is_dead = state_val in ("dead", "unavailable")
                    is_sleeping = state_val == "sleeping" or attrs.get("is_sleeping", False)

                    device = ZWaveDevice(
                        entity_id=entity_id,
                        friendly_name=friendly,
                        state=state_val,
                        is_dead=is_dead,
                        is_sleeping=is_sleeping,
                        last_seen=_parse_datetime(attrs.get("last_seen")),
                    )
                    self._devices[entity_id] = device
                except Exception:
                    logger.debug("Z-Wave Modul: Fehler beim Parsen von %s", entity_id, exc_info=True)
        except Exception:
            logger.warning("Z-Wave Modul: Fehler bei update_from_ha", exc_info=True)

    def get_status(self) -> ZWaveDashboard:
        """Erstellt das komplette Z-Wave Netzwerk-Dashboard."""
        devices_data: list[dict[str, Any]] = []
        dead_count = 0
        sleeping_count = 0

        for device in self._devices.values():
            if device.is_dead:
                dead_count += 1
            if device.is_sleeping:
                sleeping_count += 1
            devices_data.append({
                "entity_id": device.entity_id,
                "friendly_name": device.friendly_name,
                "state": device.state,
                "is_dead": device.is_dead,
                "is_sleeping": device.is_sleeping,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            })

        return ZWaveDashboard(
            controller_state=self._controller_state,
            device_count=len(self._devices),
            devices_dead=dead_count,
            devices_sleeping=sleeping_count,
            last_heal=self._last_heal,
            error_count=self._error_count,
            devices=devices_data,
        )

    def get_dashboard(self) -> ZWaveDashboard:
        """Alias fuer get_status() — Dashboard-Kompatibilitaet."""
        return self.get_status()

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_status()
        return {
            "controller_state": d.controller_state,
            "device_count": d.device_count,
            "devices_dead": d.devices_dead,
            "devices_sleeping": d.devices_sleeping,
            "last_heal": d.last_heal.isoformat() if d.last_heal else None,
            "error_count": d.error_count,
            "devices": d.devices,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        d = self.get_status()
        if d.device_count == 0 and d.controller_state == "unknown":
            return ""
        lines = [
            f"Z-Wave Netzwerk: Controller {d.controller_state}, "
            f"{d.device_count} Geraete, {d.devices_dead} tot, "
            f"{d.devices_sleeping} schlafend, {d.error_count} Fehler"
        ]
        if d.last_heal:
            lines.append(f"  Letzter Heal: {d.last_heal.isoformat()}")
        for dev in d.devices:
            if dev["is_dead"]:
                lines.append(f"  WARNUNG: {dev['friendly_name']} ist tot ({dev['entity_id']})")
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


def _safe_int(value: Any, default: int = 0) -> int:
    """Sichere Integer-Konvertierung."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
