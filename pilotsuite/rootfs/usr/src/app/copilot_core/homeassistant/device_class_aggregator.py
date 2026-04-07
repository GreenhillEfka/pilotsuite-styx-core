"""Device-Class-Aware Entity Aggregation for Habitus Zones.

Groups zone entities by HA device_class into meaningful "Sammelentitaeten"
(aggregate entities) with computed summary values for dashboard display.

Categories:
  beleuchtung  — All lights (on/off, avg brightness, scenes)
  temperatur   — Temperature sensors (avg, min, max, trend)
  heizung      — Climate devices (avg target, modes, presets)
  luftfeuchte  — Humidity sensors (avg value)
  luftqualitaet — CO2, AQI, PM2.5 sensors (avg, status)
  medien       — Media players (playing/paused, sources)
  rollladen    — Covers (avg position, open/closed count)
  strom        — Power/energy sensors (total power, trend)
  bewegung     — Motion/occupancy sensors (active count, last trigger)
  sicherheit   — Locks, alarms, door/window contacts (status overview)
  batterie     — Battery sensors (low battery alerts)
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests as http_requests

logger = logging.getLogger(__name__)


# ── Aggregate Category Definitions ──────────────────────────────────────

@dataclass(frozen=True)
class CategoryDef:
    """Definition of an aggregate category."""
    category_id: str
    name_de: str
    icon: str
    domains: tuple[str, ...]
    device_classes: tuple[str, ...] = ()  # empty = match all in domain
    unit: str = ""
    min_entities_for_aggregate: int = 1


AGGREGATE_CATEGORIES: tuple[CategoryDef, ...] = (
    CategoryDef(
        category_id="beleuchtung",
        name_de="Beleuchtung",
        icon="mdi:lightbulb-group",
        domains=("light",),
    ),
    CategoryDef(
        category_id="temperatur",
        name_de="Temperatur",
        icon="mdi:thermometer",
        domains=("sensor",),
        device_classes=("temperature",),
        unit="°C",
        min_entities_for_aggregate=1,
    ),
    CategoryDef(
        category_id="heizung",
        name_de="Heizung",
        icon="mdi:radiator",
        domains=("climate",),
    ),
    CategoryDef(
        category_id="luftfeuchte",
        name_de="Luftfeuchte",
        icon="mdi:water-percent",
        domains=("sensor",),
        device_classes=("humidity",),
        unit="%",
    ),
    CategoryDef(
        category_id="luftqualitaet",
        name_de="Luftqualitaet",
        icon="mdi:molecule-co2",
        domains=("sensor",),
        device_classes=("co2", "aqi", "pm25", "pm10", "volatile_organic_compounds"),
        unit="ppm",
    ),
    CategoryDef(
        category_id="medien",
        name_de="Medien",
        icon="mdi:television",
        domains=("media_player",),
    ),
    CategoryDef(
        category_id="rollladen",
        name_de="Rollladen",
        icon="mdi:window-shutter",
        domains=("cover",),
    ),
    CategoryDef(
        category_id="strom",
        name_de="Strom",
        icon="mdi:flash",
        domains=("sensor",),
        device_classes=("power", "energy", "current", "voltage"),
    ),
    CategoryDef(
        category_id="bewegung",
        name_de="Bewegung",
        icon="mdi:motion-sensor",
        domains=("binary_sensor",),
        device_classes=("motion", "occupancy", "presence"),
    ),
    CategoryDef(
        category_id="sicherheit",
        name_de="Sicherheit",
        icon="mdi:shield-home",
        domains=("lock", "alarm_control_panel", "binary_sensor"),
        device_classes=("door", "window", "smoke", "gas", "lock", "tamper"),
    ),
    CategoryDef(
        category_id="batterie",
        name_de="Batterien",
        icon="mdi:battery",
        domains=("sensor",),
        device_classes=("battery",),
        unit="%",
    ),
)

_CATEGORY_BY_ID: dict[str, CategoryDef] = {c.category_id: c for c in AGGREGATE_CATEGORIES}


# ── Aggregate Result ────────────────────────────────────────────────────

@dataclass
class AggregateEntity:
    """A single entity within an aggregate category."""
    entity_id: str
    friendly_name: str
    state: str
    device_class: str = ""
    unit: str = ""
    icon: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    last_updated: str = ""


@dataclass
class AggregateResult:
    """Aggregated view of entities in a single category."""
    category_id: str
    name_de: str
    icon: str
    entity_count: int
    entities: list[AggregateEntity]
    summary: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"  # ok, warning, critical, unavailable
    status_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "name_de": self.name_de,
            "icon": self.icon,
            "entity_count": self.entity_count,
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "friendly_name": e.friendly_name,
                    "state": e.state,
                    "device_class": e.device_class,
                    "unit": e.unit,
                    "icon": e.icon,
                    "last_updated": e.last_updated,
                }
                for e in self.entities
            ],
            "summary": self.summary,
            "status": self.status,
            "status_text": self.status_text,
        }


# ── Zone Aggregator ─────────────────────────────────────────────────────

class ZoneAggregator:
    """Aggregates zone entities into device-class-aware categories.

    Fetches entity states from HA Supervisor API and groups them into
    meaningful aggregate categories (Sammelentitaeten).
    """

    def __init__(self, supervisor_api: str = "", supervisor_token: str = ""):
        self._api = supervisor_api or os.environ.get(
            "SUPERVISOR_API", "http://supervisor/core/api"
        )
        self._token = supervisor_token or os.environ.get("SUPERVISOR_TOKEN", "")
        self._state_cache: dict[str, dict[str, Any]] = {}
        self._cache_ts: float = 0
        self._cache_ttl: float = 10.0  # 10s cache

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def fetch_entity_state(self, entity_id: str) -> dict[str, Any] | None:
        """Fetch single entity state from HA, with caching."""
        now = time.monotonic()
        if now - self._cache_ts < self._cache_ttl and entity_id in self._state_cache:
            return self._state_cache[entity_id]

        if not self._token:
            return None

        try:
            resp = http_requests.get(
                f"{self._api}/states/{entity_id}",
                headers=self._get_headers(),
                timeout=5,
            )
            if resp.ok:
                data = resp.json()
                self._state_cache[entity_id] = data
                return data
        except Exception:
            logger.debug("Failed to fetch state for %s", entity_id)
        return None

    def fetch_entity_states_batch(self, entity_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch states for multiple entities. Uses /states bulk if possible."""
        now = time.monotonic()

        # Check if cache is fresh enough
        if now - self._cache_ts < self._cache_ttl:
            cached = {eid: self._state_cache[eid] for eid in entity_ids if eid in self._state_cache}
            if len(cached) == len(entity_ids):
                return cached

        if not self._token:
            return {}

        # Fetch all states and filter
        try:
            resp = http_requests.get(
                f"{self._api}/states",
                headers=self._get_headers(),
                timeout=10,
            )
            if resp.ok:
                all_states = resp.json()
                entity_set = set(entity_ids)
                result = {}
                for state in all_states:
                    eid = state.get("entity_id", "")
                    if eid in entity_set:
                        self._state_cache[eid] = state
                        result[eid] = state
                self._cache_ts = time.monotonic()
                return result
        except Exception:
            logger.debug("Failed to batch fetch entity states")

        # Fallback: individual fetches
        result = {}
        for eid in entity_ids:
            state = self.fetch_entity_state(eid)
            if state:
                result[eid] = state
        return result

    def aggregate_zone(
        self, entity_ids: list[str], entity_states: dict[str, dict[str, Any]] | None = None,
    ) -> list[AggregateResult]:
        """Aggregate zone entities into device-class categories.

        Args:
            entity_ids: List of entity_ids assigned to the zone.
            entity_states: Pre-fetched entity states (optional, fetched if not provided).

        Returns:
            List of AggregateResult, one per category that has matching entities.
        """
        if entity_states is None:
            entity_states = self.fetch_entity_states_batch(entity_ids)

        # Classify entities into categories
        classified: dict[str, list[tuple[str, dict[str, Any]]]] = {
            cat.category_id: [] for cat in AGGREGATE_CATEGORIES
        }
        unclassified: list[tuple[str, dict[str, Any]]] = []

        for eid in entity_ids:
            state = entity_states.get(eid)
            if not state:
                continue
            domain = eid.split(".", 1)[0] if "." in eid else ""
            device_class = state.get("attributes", {}).get("device_class", "")

            matched = False
            for cat in AGGREGATE_CATEGORIES:
                if domain not in cat.domains:
                    continue
                if cat.device_classes and device_class not in cat.device_classes:
                    continue
                classified[cat.category_id].append((eid, state))
                matched = True
                break

            if not matched:
                unclassified.append((eid, state))

        # Build aggregate results
        results: list[AggregateResult] = []
        for cat in AGGREGATE_CATEGORIES:
            entities_in_cat = classified[cat.category_id]
            if not entities_in_cat:
                continue
            if len(entities_in_cat) < cat.min_entities_for_aggregate:
                continue

            agg_entities = []
            for eid, state in entities_in_cat:
                attrs = state.get("attributes", {})
                agg_entities.append(AggregateEntity(
                    entity_id=eid,
                    friendly_name=attrs.get("friendly_name", eid),
                    state=state.get("state", "unknown"),
                    device_class=attrs.get("device_class", ""),
                    unit=attrs.get("unit_of_measurement", cat.unit),
                    icon=attrs.get("icon", cat.icon),
                    attributes=attrs,
                    last_updated=state.get("last_updated", ""),
                ))

            summary = _compute_summary(cat.category_id, agg_entities)
            status, status_text = _compute_status(cat.category_id, agg_entities, summary)

            results.append(AggregateResult(
                category_id=cat.category_id,
                name_de=cat.name_de,
                icon=cat.icon,
                entity_count=len(agg_entities),
                entities=agg_entities,
                summary=summary,
                status=status,
                status_text=status_text,
            ))

        return results

    def get_category_defs(self) -> list[dict[str, Any]]:
        """Return all category definitions for configuration UI."""
        return [
            {
                "category_id": cat.category_id,
                "name_de": cat.name_de,
                "icon": cat.icon,
                "domains": list(cat.domains),
                "device_classes": list(cat.device_classes),
                "unit": cat.unit,
            }
            for cat in AGGREGATE_CATEGORIES
        ]

    def invalidate_cache(self) -> None:
        """Force cache refresh on next query."""
        self._cache_ts = 0


# ── Summary Computation ────────────────────────────────────────────────

def _safe_float(val: Any) -> float | None:
    """Try to parse a float from entity state value."""
    if val is None or val in ("unknown", "unavailable", ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _compute_summary(category_id: str, entities: list[AggregateEntity]) -> dict[str, Any]:
    """Compute summary statistics for a category."""
    if category_id == "beleuchtung":
        return _summarize_lights(entities)
    elif category_id == "temperatur":
        return _summarize_numeric(entities, "°C")
    elif category_id == "heizung":
        return _summarize_climate(entities)
    elif category_id in ("luftfeuchte", "luftqualitaet", "batterie"):
        return _summarize_numeric(entities, entities[0].unit if entities else "%")
    elif category_id == "medien":
        return _summarize_media(entities)
    elif category_id == "rollladen":
        return _summarize_covers(entities)
    elif category_id == "strom":
        return _summarize_power(entities)
    elif category_id == "bewegung":
        return _summarize_motion(entities)
    elif category_id == "sicherheit":
        return _summarize_security(entities)
    return {}


def _summarize_lights(entities: list[AggregateEntity]) -> dict[str, Any]:
    on_count = sum(1 for e in entities if e.state == "on")
    brightnesses = []
    color_temps = []
    for e in entities:
        if e.state == "on":
            b = e.attributes.get("brightness")
            if b is not None:
                brightnesses.append(round(int(b) / 255 * 100))
            ct = e.attributes.get("color_temp_kelvin")
            if ct is not None:
                color_temps.append(int(ct))
    return {
        "on_count": on_count,
        "off_count": len(entities) - on_count,
        "total": len(entities),
        "all_on": on_count == len(entities),
        "all_off": on_count == 0,
        "avg_brightness_pct": round(sum(brightnesses) / len(brightnesses)) if brightnesses else 0,
        "avg_color_temp_k": round(sum(color_temps) / len(color_temps)) if color_temps else 0,
    }


def _summarize_numeric(entities: list[AggregateEntity], unit: str) -> dict[str, Any]:
    values = []
    for e in entities:
        v = _safe_float(e.state)
        if v is not None:
            values.append(v)
    if not values:
        return {"available": False}
    avg_val = sum(values) / len(values)
    return {
        "avg": round(avg_val, 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "spread": round(max(values) - min(values), 1),
        "unit": unit,
        "sensor_count": len(values),
        "available": True,
    }


def _summarize_climate(entities: list[AggregateEntity]) -> dict[str, Any]:
    current_temps = []
    target_temps = []
    modes = []
    heating_count = 0
    for e in entities:
        t = _safe_float(e.attributes.get("current_temperature"))
        if t is not None:
            current_temps.append(t)
        tt = _safe_float(e.attributes.get("temperature"))
        if tt is not None:
            target_temps.append(tt)
        mode = e.attributes.get("hvac_mode", e.state)
        modes.append(mode)
        if mode in ("heat", "auto"):
            heating_count += 1
    return {
        "avg_current_temp": round(sum(current_temps) / len(current_temps), 1) if current_temps else None,
        "avg_target_temp": round(sum(target_temps) / len(target_temps), 1) if target_temps else None,
        "heating_count": heating_count,
        "total": len(entities),
        "modes": list(set(modes)),
        "all_off": all(m == "off" for m in modes),
    }


def _summarize_media(entities: list[AggregateEntity]) -> dict[str, Any]:
    playing = [e for e in entities if e.state == "playing"]
    paused = [e for e in entities if e.state == "paused"]
    idle = [e for e in entities if e.state in ("idle", "standby", "off")]
    now_playing = None
    if playing:
        p = playing[0]
        now_playing = {
            "entity_id": p.entity_id,
            "title": p.attributes.get("media_title", ""),
            "artist": p.attributes.get("media_artist", ""),
            "source": p.attributes.get("source", ""),
        }
    return {
        "playing_count": len(playing),
        "paused_count": len(paused),
        "idle_count": len(idle),
        "total": len(entities),
        "now_playing": now_playing,
    }


def _summarize_covers(entities: list[AggregateEntity]) -> dict[str, Any]:
    open_count = sum(1 for e in entities if e.state == "open")
    positions = []
    for e in entities:
        p = _safe_float(e.attributes.get("current_position"))
        if p is not None:
            positions.append(p)
    return {
        "open_count": open_count,
        "closed_count": len(entities) - open_count,
        "total": len(entities),
        "avg_position_pct": round(sum(positions) / len(positions)) if positions else None,
        "all_open": open_count == len(entities),
        "all_closed": open_count == 0,
    }


def _summarize_power(entities: list[AggregateEntity]) -> dict[str, Any]:
    power_values = []
    energy_values = []
    for e in entities:
        v = _safe_float(e.state)
        if v is None:
            continue
        if e.device_class == "power":
            power_values.append(v)
        elif e.device_class == "energy":
            energy_values.append(v)
        else:
            power_values.append(v)  # default to power
    return {
        "total_power_w": round(sum(power_values), 1) if power_values else None,
        "total_energy_kwh": round(sum(energy_values), 2) if energy_values else None,
        "sensor_count": len(entities),
    }


def _summarize_motion(entities: list[AggregateEntity]) -> dict[str, Any]:
    active_count = sum(1 for e in entities if e.state == "on")
    latest_update = ""
    for e in entities:
        if e.last_updated and e.last_updated > latest_update:
            latest_update = e.last_updated
    return {
        "active_count": active_count,
        "total": len(entities),
        "any_active": active_count > 0,
        "last_triggered": latest_update,
    }


def _summarize_security(entities: list[AggregateEntity]) -> dict[str, Any]:
    open_contacts = []
    locked_count = 0
    alarm_state = None
    for e in entities:
        dc = e.device_class
        if dc in ("door", "window"):
            if e.state == "on":
                open_contacts.append(e.friendly_name)
        elif dc == "lock" or e.entity_id.startswith("lock."):
            if e.state == "locked":
                locked_count += 1
        elif e.entity_id.startswith("alarm_control_panel."):
            alarm_state = e.state
        elif dc in ("smoke", "gas"):
            if e.state == "on":
                open_contacts.append(f"{e.friendly_name} (Alarm!)")
    return {
        "open_contacts": open_contacts,
        "open_count": len(open_contacts),
        "locked_count": locked_count,
        "alarm_state": alarm_state,
        "total": len(entities),
        "all_secure": len(open_contacts) == 0,
    }


# ── Status Computation ──────────────────────────────────────────────────

def _compute_status(
    category_id: str, entities: list[AggregateEntity], summary: dict[str, Any],
) -> tuple[str, str]:
    """Compute health status for a category. Returns (status, status_text)."""
    unavailable_count = sum(1 for e in entities if e.state in ("unavailable", "unknown"))
    if unavailable_count == len(entities):
        return "unavailable", f"Alle {len(entities)} Geraete nicht erreichbar"
    if unavailable_count > 0:
        return "warning", f"{unavailable_count}/{len(entities)} nicht erreichbar"

    if category_id == "batterie":
        low = [e for e in entities if (_safe_float(e.state) or 100) < 20]
        if low:
            names = ", ".join(e.friendly_name for e in low[:3])
            return "warning", f"Batterie niedrig: {names}"

    if category_id == "sicherheit":
        if summary.get("open_count", 0) > 0:
            return "warning", f"{summary['open_count']} Kontakt(e) offen"

    if category_id == "luftqualitaet":
        avg = summary.get("avg")
        if avg is not None and avg > 1500:
            return "critical", f"CO2 hoch: {avg} ppm"
        if avg is not None and avg > 1000:
            return "warning", f"CO2 erhoht: {avg} ppm"

    return "ok", ""
