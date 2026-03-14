"""Zone Health API — Per-zone health monitoring and diagnostics.

Provides health status, entity availability checks, and diagnostic
information for each Habitus zone.

Endpoints:
  GET /api/v1/zone/health              - Health overview for all zones
  GET /api/v1/zone/health/<zone_id>    - Detailed health for a specific zone
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

zone_health_bp = Blueprint("zone_health", __name__, url_prefix="/api/v1/zone/health")

_svc: dict[str, Any] = {}


def init_zone_health_api(**services: Any) -> None:
    """Initialize Zone Health API with service references."""
    _svc.clear()
    _svc.update(services)
    logger.info("Zone Health API initialized")


# ── Data Models ─────────────────────────────────────────────────────────

@dataclass
class EntityHealth:
    """Health status of a single entity."""
    entity_id: str
    friendly_name: str
    domain: str
    state: str
    available: bool
    last_updated: str = ""
    last_changed: str = ""
    stale: bool = False  # True if last_updated > 1h ago
    issues: list[str] = field(default_factory=list)


@dataclass
class ZoneHealthResult:
    """Health status for a single zone."""
    zone_id: str
    zone_name: str
    health_score: int  # 0-100
    status: str  # healthy, degraded, critical, unknown
    total_entities: int = 0
    available_entities: int = 0
    unavailable_entities: int = 0
    stale_entities: int = 0
    entity_details: list[EntityHealth] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    automation_mode: str = "unknown"
    module_states: dict[str, str] = field(default_factory=dict)
    event_coverage: dict[str, bool] = field(default_factory=dict)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "health_score": self.health_score,
            "status": self.status,
            "total_entities": self.total_entities,
            "available_entities": self.available_entities,
            "unavailable_entities": self.unavailable_entities,
            "stale_entities": self.stale_entities,
            "issues": self.issues,
            "automation_mode": self.automation_mode,
            "module_states": self.module_states,
            "event_coverage": self.event_coverage,
            "checked_at": self.checked_at,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        d["entity_details"] = [
            {
                "entity_id": e.entity_id,
                "friendly_name": e.friendly_name,
                "domain": e.domain,
                "state": e.state,
                "available": e.available,
                "last_updated": e.last_updated,
                "stale": e.stale,
                "issues": e.issues,
            }
            for e in self.entity_details
        ]
        return d


# ── Health Checker ──────────────────────────────────────────────────────

class ZoneHealthChecker:
    """Checks health status of Habitus zones."""

    STALE_THRESHOLD_S = 3600  # 1 hour

    # Required entity roles for a "healthy" zone
    EXPECTED_ROLES = {
        "lights": "Beleuchtung",
        "motion": "Bewegung",
        "climate": "Heizung",
        "sensors": "Sensoren",
    }

    def __init__(self):
        self._api = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        self._token = os.environ.get("SUPERVISOR_TOKEN", "")

    def check_zone(self, zone: dict[str, Any], *, prefetched_states: dict[str, dict[str, Any]] | None = None) -> ZoneHealthResult:
        """Check health status for a single zone.

        Args:
            zone: Zone config dict with zone_id, entity_ids, entities.
            prefetched_states: Optional pre-fetched states dict keyed by entity_id.
                If provided, avoids a separate /states API call.
        """
        zone_id = zone.get("zone_id", "")
        zone_name = zone.get("name_de", zone.get("name", zone_id))
        entity_ids = zone.get("entity_ids", [])
        entities_by_role = zone.get("entities", {})

        now = datetime.now(timezone.utc)
        result = ZoneHealthResult(
            zone_id=zone_id,
            zone_name=zone_name,
            health_score=100,
            status="healthy",
            total_entities=len(entity_ids),
            checked_at=now.isoformat(),
        )

        if not entity_ids:
            result.health_score = 0
            result.status = "unknown"
            result.issues.append("Keine Entitaeten zugewiesen")
            return result

        # Use prefetched states if available, otherwise fetch per-zone
        if prefetched_states is not None:
            entity_set = set(entity_ids)
            entity_states = {eid: s for eid, s in prefetched_states.items() if eid in entity_set}
        else:
            entity_states = self._fetch_entity_states(entity_ids)

        # Check each entity
        for eid in entity_ids:
            state = entity_states.get(eid)
            domain = eid.split(".", 1)[0] if "." in eid else ""

            if state is None:
                eh = EntityHealth(
                    entity_id=eid,
                    friendly_name=eid,
                    domain=domain,
                    state="not_found",
                    available=False,
                    issues=["Entitaet nicht in HA gefunden"],
                )
                result.unavailable_entities += 1
                result.entity_details.append(eh)
                continue

            attrs = state.get("attributes", {})
            entity_state = state.get("state", "unknown")
            friendly_name = attrs.get("friendly_name", eid)
            last_updated = state.get("last_updated", "")
            last_changed = state.get("last_changed", "")

            available = entity_state not in ("unavailable", "unknown")
            issues = []

            # Check staleness
            stale = False
            if last_updated:
                try:
                    lu = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    age_s = (now - lu).total_seconds()
                    if age_s > self.STALE_THRESHOLD_S:
                        stale = True
                        issues.append(f"Letztes Update vor {int(age_s / 60)} Minuten")
                except (ValueError, TypeError):
                    pass

            if not available:
                issues.append(f"Status: {entity_state}")
                result.unavailable_entities += 1
            else:
                result.available_entities += 1

            if stale:
                result.stale_entities += 1

            result.entity_details.append(EntityHealth(
                entity_id=eid,
                friendly_name=friendly_name,
                domain=domain,
                state=entity_state,
                available=available,
                last_updated=last_updated,
                last_changed=last_changed,
                stale=stale,
                issues=issues,
            ))

        # Check event coverage (does zone have required entity roles?)
        for role, role_name in self.EXPECTED_ROLES.items():
            has_role = bool(entities_by_role.get(role))
            result.event_coverage[role] = has_role
            if not has_role:
                result.issues.append(f"Fehlende Rolle: {role_name}")

        # Get automation mode
        za = _svc.get("zone_automation")
        if za:
            try:
                mode = za.get_automation_mode(zone_id)
                result.automation_mode = mode or "off"
            except Exception:
                pass

        # Get module states
        module_registry = _svc.get("module_registry")
        if module_registry and hasattr(module_registry, "get_zone_states"):
            try:
                result.module_states = module_registry.get_zone_states(zone_id)
            except Exception:
                pass

        # Compute health score
        result.health_score = self._compute_score(result)
        result.status = self._score_to_status(result.health_score)

        return result

    def check_all_zones(self) -> list[ZoneHealthResult]:
        """Check health for all configured zones (single /states fetch)."""
        zones = self._get_zones()
        all_states = self._fetch_all_states()
        return [self.check_zone(zone, prefetched_states=all_states) for zone in zones]

    def _compute_score(self, result: ZoneHealthResult) -> int:
        """Compute health score (0-100) from zone health data."""
        if result.total_entities == 0:
            return 0

        score = 100

        # Deduct for unavailable entities (-10 per entity, max -40)
        unavailable_pct = result.unavailable_entities / result.total_entities
        score -= min(40, int(unavailable_pct * 100))

        # Deduct for stale entities (-5 per entity, max -20)
        stale_pct = result.stale_entities / result.total_entities
        score -= min(20, int(stale_pct * 50))

        # Deduct for missing roles (-5 per missing role)
        missing_roles = sum(1 for v in result.event_coverage.values() if not v)
        score -= missing_roles * 5

        # Deduct for non-role issues only (avoid double-counting missing roles)
        non_role_issues = [i for i in result.issues if not i.startswith("Fehlende Rolle:")]
        score -= min(20, len(non_role_issues) * 3)

        return max(0, min(100, score))

    def _score_to_status(self, score: int) -> str:
        if score >= 80:
            return "healthy"
        elif score >= 50:
            return "degraded"
        elif score > 0:
            return "critical"
        return "unknown"

    def _fetch_all_states(self) -> dict[str, dict[str, Any]]:
        """Fetch all entity states from HA Supervisor API, keyed by entity_id."""
        if not self._token:
            return {}
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        try:
            resp = http_requests.get(
                f"{self._api}/states",
                headers=headers,
                timeout=10,
            )
            if resp.ok:
                return {
                    s["entity_id"]: s
                    for s in resp.json()
                    if "entity_id" in s
                }
        except Exception:
            logger.debug("Failed to fetch all entity states for health check")
        return {}

    def _fetch_entity_states(self, entity_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch entity states from HA Supervisor API."""
        if not self._token:
            return {}
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        try:
            resp = http_requests.get(
                f"{self._api}/states",
                headers=headers,
                timeout=10,
            )
            if resp.ok:
                entity_set = set(entity_ids)
                return {
                    s["entity_id"]: s
                    for s in resp.json()
                    if s.get("entity_id") in entity_set
                }
        except Exception:
            logger.debug("Failed to fetch entity states for health check")
        return {}

    def _get_zones(self) -> list[dict[str, Any]]:
        """Get zone configurations."""
        za = _svc.get("zone_automation")
        if za and hasattr(za, "get_all_states"):
            try:
                states = za.get_all_states()
                zones = []
                for s in states:
                    zid = s.get("zone_id", "")
                    entities = {}
                    if hasattr(za, "get_zone_entities_by_role"):
                        entities = za.get_zone_entities_by_role(zid) or {}
                    entity_ids = [
                        eid for role_list in entities.values()
                        if isinstance(role_list, list)
                        for eid in role_list
                    ]
                    zones.append({
                        "zone_id": zid,
                        "name_de": s.get("name", zid),
                        "entity_ids": entity_ids,
                        "entities": entities,
                    })
                return zones
            except Exception:
                pass

        # Fallback to habitus_zones
        try:
            from copilot_core.homeassistant.habitus_zones import get_all_zones
            zones_raw = get_all_zones()
            try:
                from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES
            except ImportError:
                EXAMPLE_ZONE_ENTITIES = {}

            zones = []
            for z in zones_raw:
                if isinstance(z, dict):
                    zid = z.get("zone_id", "")
                    zdict = z
                else:
                    zid = getattr(z, "zone_type", "")
                    if hasattr(zid, "value"):
                        zid = zid.value
                    zdict = {
                        "zone_id": zid,
                        "name_de": getattr(z, "name_de", zid),
                    }
                entities = EXAMPLE_ZONE_ENTITIES.get(zid, {})
                entity_ids = [
                    eid for role_list in entities.values()
                    if isinstance(role_list, list)
                    for eid in role_list
                ]
                zdict["entity_ids"] = entity_ids
                zdict["entities"] = entities
                zones.append(zdict)
            return zones
        except ImportError:
            return []


# ── REST Endpoints ──────────────────────────────────────────────────────

_checker: ZoneHealthChecker | None = None


def _get_checker() -> ZoneHealthChecker:
    global _checker
    if _checker is None:
        _checker = ZoneHealthChecker()
    return _checker


@zone_health_bp.route("", methods=["GET"])
@require_token
def get_all_zone_health():
    """Health overview for all zones."""
    checker = _get_checker()
    results = checker.check_all_zones()
    return jsonify({
        "ok": True,
        "zones": [r.to_dict() for r in results],
        "summary": {
            "total_zones": len(results),
            "healthy": sum(1 for r in results if r.status == "healthy"),
            "degraded": sum(1 for r in results if r.status == "degraded"),
            "critical": sum(1 for r in results if r.status == "critical"),
            "unknown": sum(1 for r in results if r.status == "unknown"),
            "avg_score": round(sum(r.health_score for r in results) / len(results)) if results else 0,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_health_bp.route("/<zone_id>", methods=["GET"])
@require_token
def get_zone_health_detail(zone_id: str):
    """Detailed health for a specific zone (includes entity-level details)."""
    checker = _get_checker()
    zones = checker._get_zones()
    zone_id_norm = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"
    zone = next(
        (z for z in zones if z.get("zone_id") in (zone_id, zone_id_norm, f"zone:{zone_id}")),
        None,
    )
    if zone is None:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' nicht gefunden"}), 404

    result = checker.check_zone(zone)
    return jsonify({
        "ok": True,
        "zone": result.to_detail_dict(),
    })
