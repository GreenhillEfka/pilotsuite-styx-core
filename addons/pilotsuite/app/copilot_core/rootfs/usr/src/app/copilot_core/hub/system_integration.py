"""System Integration Hub — Cross-Engine Communication (v7.3.0).

Wires all PilotSuite engines together for real-time cross-module communication:
- Presence change → Scene suggestions update, media follow, notifications
- Zone mode change → Light intelligence, media, notifications suppression
- Energy threshold → Notification, scene suggestion
- Anomaly detected → Notification, maintenance check
- Scene activated → Light, media, climate, zone mode cascade
- Person arrives/departs → Presence update, scene suggest, notification

This is the orchestration layer that makes all modules work together as one system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntegrationEvent:
    """An event flowing through the integration hub."""

    event_type: str
    source_engine: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    handled_by: list[str] = field(default_factory=list)


@dataclass
class IntegrationStatus:
    """Status of the integration hub."""

    engines_connected: int = 0
    events_processed: int = 0
    last_event: str = ""
    last_event_time: str = ""
    engine_names: list[str] = field(default_factory=list)
    active_subscriptions: int = 0
    event_log: list[dict[str, Any]] = field(default_factory=list)


class SystemIntegrationHub:
    """Orchestration layer connecting all PilotSuite engines."""

    def __init__(self) -> None:
        self._engines: dict[str, object] = {}
        self._event_log: list[IntegrationEvent] = []
        self._subscriptions: dict[str, list[str]] = {}  # event_type → [engine_names]
        self._events_processed = 0

    # ── Engine registration ───────────────────────────────────────────────

    def register_engine(self, name: str, engine: object) -> None:
        """Register an engine for cross-module communication."""
        self._engines[name] = engine
        logger.info("Integration Hub: registered engine '%s'", name)

    def get_engine(self, name: str) -> object | None:
        """Get a registered engine by name."""
        return self._engines.get(name)

    # ── Event subscriptions ───────────────────────────────────────────────

    def subscribe(self, event_type: str, engine_name: str) -> None:
        """Subscribe an engine to an event type."""
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        if engine_name not in self._subscriptions[event_type]:
            self._subscriptions[event_type].append(engine_name)

    def unsubscribe(self, event_type: str, engine_name: str) -> None:
        """Unsubscribe an engine from an event type."""
        if event_type in self._subscriptions:
            self._subscriptions[event_type] = [
                n for n in self._subscriptions[event_type] if n != engine_name
            ]

    # ── Event dispatch ────────────────────────────────────────────────────

    def dispatch(self, event_type: str, source: str,
                 data: dict[str, Any] | None = None) -> IntegrationEvent:
        """Dispatch an event to all subscribed engines."""
        event = IntegrationEvent(
            event_type=event_type,
            source_engine=source,
            data=data or {},
        )

        handlers = self._subscriptions.get(event_type, [])
        for engine_name in handlers:
            if engine_name == source:
                continue  # skip source to avoid loops
            try:
                self._handle_event(engine_name, event)
                event.handled_by.append(engine_name)
            except Exception as e:
                logger.warning("Integration Hub: handler '%s' failed for '%s': %s",
                               engine_name, event_type, e)

        self._events_processed += 1
        self._event_log.append(event)
        self._event_log = self._event_log[-200:]

        logger.info("Integration Hub: dispatched '%s' from '%s' → handled by %d engines",
                     event_type, source, len(event.handled_by))
        return event

    def _handle_event(self, engine_name: str, event: IntegrationEvent) -> None:
        """Handle an event for a specific engine."""
        engine = self._engines.get(engine_name)
        if not engine:
            return

        et = event.event_type
        data = event.data

        # ── Presence events → Scene, Media, Notification ──────────────
        if et == "presence_changed":
            if engine_name == "scene_intelligence" and hasattr(engine, "suggest_scenes"):
                from .scene_intelligence import SceneContext
                ctx = SceneContext(
                    hour=data.get("hour", 12),
                    is_home=data.get("is_home", True),
                    occupancy_count=data.get("occupancy_count", 1),
                    active_zone=data.get("zone_id", ""),
                )
                engine.suggest_scenes(ctx, limit=3)

            elif engine_name == "media_follow" and hasattr(engine, "on_zone_enter"):
                zone_id = data.get("zone_id", "")
                if zone_id and data.get("is_home", True):
                    engine.on_zone_enter(zone_id)

            elif engine_name == "notification_intelligence" and hasattr(engine, "send"):
                person = data.get("person_id", "")
                is_home = data.get("is_home", True)
                if person:
                    action = "angekommen" if is_home else "gegangen"
                    engine.send(
                        title=f"Anwesenheit: {person}",
                        message=f"{person} ist {action}",
                        priority="info",
                        category="presence",
                        person_id=person,
                    )

        # ── Zone mode changed → Light, Media, Notification ───────────
        elif et == "zone_mode_changed":
            zone_id = data.get("zone_id", "")
            mode_id = data.get("mode_id", "")

            if engine_name == "light_intelligence" and hasattr(engine, "set_active_scene"):
                # Map zone modes to light scenes
                mode_scene_map = {
                    "movie": "movie", "romantic": "romantic",
                    "party": "party", "night": "night",
                    "focus": "focus", "relax": "relax",
                }
                if mode_id in mode_scene_map:
                    engine.set_active_scene(mode_scene_map[mode_id], zone_id)

            elif engine_name == "notification_intelligence" and hasattr(engine, "set_dnd"):
                dnd_modes = {"night", "focus", "movie", "sleeping"}
                if mode_id in dnd_modes:
                    engine.set_dnd(enabled=True, zone_mode=mode_id)
                else:
                    engine.set_dnd(enabled=False, zone_mode=mode_id)

        # ── Scene activated → Light, Media, Zone Mode cascade ─────────
        elif et == "scene_activated":
            scene_data = data.get("scene", {})
            zone_id = data.get("zone_id", "")

            if engine_name == "zone_modes" and hasattr(engine, "activate_mode"):
                mode = scene_data.get("zone_mode")
                if mode and zone_id:
                    engine.activate_mode(zone_id=zone_id, mode_id=mode)

            elif engine_name == "notification_intelligence" and hasattr(engine, "send"):
                name = scene_data.get("name_de", "Szene")
                if scene_data.get("suppress_automations"):
                    engine.set_dnd(enabled=True, zone_mode="scene")
                engine.send(
                    title="Szene aktiviert",
                    message=f"{name} wurde aktiviert",
                    priority="info",
                    category="scene",
                )

        # ── Anomaly detected → Notification, Maintenance ─────────────
        elif et == "anomaly_detected":
            if engine_name == "notification_intelligence" and hasattr(engine, "send"):
                severity = data.get("severity", "info")
                entity = data.get("entity_id", "Unbekannt")
                priority_map = {"critical": "critical", "high": "high",
                                "medium": "normal", "low": "low"}
                engine.send(
                    title=f"Anomalie: {entity}",
                    message=data.get("message", "Anomalie erkannt"),
                    priority=priority_map.get(severity, "normal"),
                    category="anomaly",
                    icon="mdi:alert-circle",
                )

            elif engine_name == "predictive_maintenance" and hasattr(engine, "evaluate_all"):
                engine.evaluate_all()

        # ── Energy threshold → Notification, Scene suggestion ─────────
        elif et == "energy_threshold":
            if engine_name == "notification_intelligence" and hasattr(engine, "send"):
                kwh = data.get("daily_kwh", 0)
                engine.send(
                    title="Energieverbrauch hoch",
                    message=f"Tagesverbrauch: {kwh:.1f} kWh",
                    priority="high",
                    category="energy",
                    icon="mdi:flash-alert",
                )

            elif engine_name == "scene_intelligence" and hasattr(engine, "suggest_scenes"):
                from .scene_intelligence import SceneContext
                ctx = SceneContext(hour=data.get("hour", 12))
                engine.suggest_scenes(ctx, limit=3)

        # ── Person arrived/departed → Full cascade ────────────────────
        elif et == "person_arrived":
            if engine_name == "scene_intelligence" and hasattr(engine, "suggest_scenes"):
                from .scene_intelligence import SceneContext
                ctx = SceneContext(
                    hour=data.get("hour", 12),
                    is_home=True,
                    occupancy_count=data.get("occupancy_count", 1),
                )
                engine.suggest_scenes(ctx, limit=3)

        elif et == "person_departed":
            if engine_name == "scene_intelligence" and hasattr(engine, "activate_scene"):
                # Suggest away scene if nobody home
                if data.get("occupancy_count", 0) == 0:
                    engine.activate_scene("away")

            elif engine_name == "energy_advisor" and hasattr(engine, "calculate_eco_score"):
                engine.calculate_eco_score()

    # ── Auto-wiring ──────────────────────────────────────────────────────

    def auto_wire(self) -> int:
        """Automatically wire all registered engines with default subscriptions.

        Returns the number of subscriptions created.
        """
        wiring = {
            "presence_changed": [
                "scene_intelligence", "media_follow", "notification_intelligence",
            ],
            "zone_mode_changed": [
                "light_intelligence", "notification_intelligence",
            ],
            "scene_activated": [
                "zone_modes", "notification_intelligence",
            ],
            "anomaly_detected": [
                "notification_intelligence", "predictive_maintenance",
            ],
            "energy_threshold": [
                "notification_intelligence", "scene_intelligence",
            ],
            "person_arrived": [
                "scene_intelligence",
            ],
            "person_departed": [
                "scene_intelligence", "energy_advisor",
            ],
        }

        count = 0
        for event_type, engine_names in wiring.items():
            for name in engine_names:
                if name in self._engines:
                    self.subscribe(event_type, name)
                    count += 1

        logger.info("Integration Hub: auto-wired %d subscriptions for %d engines",
                     count, len(self._engines))
        return count

    # ── Query ────────────────────────────────────────────────────────────

    def get_status(self) -> IntegrationStatus:
        """Get integration hub status."""
        total_subs = sum(len(v) for v in self._subscriptions.values())
        last_event = self._event_log[-1] if self._event_log else None

        return IntegrationStatus(
            engines_connected=len(self._engines),
            events_processed=self._events_processed,
            last_event=last_event.event_type if last_event else "",
            last_event_time=last_event.timestamp.isoformat() if last_event else "",
            engine_names=list(self._engines.keys()),
            active_subscriptions=total_subs,
            event_log=[
                {
                    "event_type": e.event_type,
                    "source": e.source_engine,
                    "handled_by": e.handled_by,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in reversed(self._event_log[-10:])
            ],
        )

    def get_wiring_diagram(self) -> dict[str, list[str]]:
        """Get the current wiring diagram (event → subscribers)."""
        return {k: list(v) for k, v in self._subscriptions.items()}
