"""Autonomy Executor — Mood-driven, zone-aware auto-execution orchestrator.

Central component that listens to bus events (mood.changed, presence.changed)
and executes actions through HA Bridge / MusikwolkeBridge when governance
checks pass (zone mode + module state double-safety).
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# Rate limiting: max 1 action per module per zone per N seconds
_RATE_LIMIT_SECONDS = 30


@dataclass
class ExecutionResult:
    """Result of an autonomy execution attempt."""

    zone_id: str
    module_id: str
    decision: str  # "executed" | "suggested" | "skipped"
    reason: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutonomyExecutor:
    """Orchestrates autonomous action execution based on mood and presence events.

    Double-Safety checks:
    1. Zone automation_mode == "autonomy"
    2. Source module == "active" in zone
    3. Target module == "active" in zone
    """

    def __init__(
        self,
        zone_automation=None,
        module_registry=None,
        ha_bridge=None,
        behavioral_log=None,
        light_intelligence=None,
        musikwolke_bridge=None,
        neuron_manager=None,
        bus=None,
    ) -> None:
        self._zone_automation = zone_automation
        self._module_registry = module_registry
        self._ha_bridge = ha_bridge
        self._behavioral_log = behavioral_log
        self._light_intelligence = light_intelligence
        self._musikwolke_bridge = musikwolke_bridge
        self._neuron_manager = neuron_manager
        self._bus = bus

        # Lazy import to avoid circular deps
        self._mood_mapper = None

        # Rate limiting: (zone_id, module_id) → last_execution_timestamp
        self._rate_limits: Dict[str, float] = {}

        # Stats
        self._stats = {
            "total_events": 0,
            "executed": 0,
            "suggested": 0,
            "skipped": 0,
            "errors": 0,
        }

        _LOGGER.info("AutonomyExecutor initialized")

    def _get_mood_mapper(self):
        """Lazy-init MoodActionMapper."""
        if self._mood_mapper is None:
            from copilot_core.autonomy.mood_actions import MoodActionMapper
            self._mood_mapper = MoodActionMapper()
        return self._mood_mapper

    # ── Rate Limiting ───────────────────────────────────────────────────

    def _is_rate_limited(self, zone_id: str, module_id: str) -> bool:
        """Check if action is rate-limited (30s cooldown per zone+module)."""
        key = f"{zone_id}:{module_id}"
        last = self._rate_limits.get(key, 0)
        return (time.time() - last) < _RATE_LIMIT_SECONDS

    def _record_execution(self, zone_id: str, module_id: str) -> None:
        """Record execution timestamp for rate limiting."""
        key = f"{zone_id}:{module_id}"
        self._rate_limits[key] = time.time()

    # ── Governance Check ────────────────────────────────────────────────

    def execute_if_allowed(
        self,
        zone_id: str,
        module_id: str,
        actions: List[Dict[str, Any]],
        reason: str,
        context: Dict[str, Any] | None = None,
        source_module: str = "mood",
    ) -> ExecutionResult:
        """Check governance and execute actions if allowed.

        Decision flow:
        1. Zone automation_mode check (off → SKIP, learning → SUGGEST, autonomy → continue)
        2. Module state check via registry (per-zone or global fallback)
        3. Double-safety: both source + target must be active
        4. Rate limiting check

        Args:
            zone_id: Target zone.
            module_id: Target module (e.g. "licht", "musik").
            actions: List of action dicts to execute.
            reason: Human-readable reason for the action.
            context: Additional context (mood, confidence, weather, etc.).
            source_module: Source module that triggered this (default: "mood").

        Returns:
            ExecutionResult with decision and details.
        """
        context = context or {}
        self._stats["total_events"] += 1

        # 1. Zone automation mode check
        zone_mode = "off"
        if self._zone_automation:
            zone_mode = self._zone_automation.get_automation_mode(zone_id)

        if zone_mode == "off":
            self._stats["skipped"] += 1
            return ExecutionResult(
                zone_id=zone_id, module_id=module_id,
                decision="skipped", reason=f"Zone mode is 'off'",
            )

        if zone_mode == "learning":
            self._stats["suggested"] += 1
            self._log_action(
                zone_id, module_id, actions, reason, context,
                result="would_have_executed", source_module=source_module,
            )
            return ExecutionResult(
                zone_id=zone_id, module_id=module_id,
                decision="suggested", reason="Zone mode is 'learning' — logged as suggestion",
                actions=actions,
            )

        # 2. Module state check (per-zone with global fallback)
        target_state = "active"
        source_state = "active"
        if self._module_registry:
            target_state = self._module_registry.get_zone_state(zone_id, module_id)
            source_state = self._module_registry.get_zone_state(zone_id, source_module)

        if target_state == "off" or source_state == "off":
            self._stats["skipped"] += 1
            return ExecutionResult(
                zone_id=zone_id, module_id=module_id,
                decision="skipped",
                reason=f"Module off (source={source_module}:{source_state}, target={module_id}:{target_state})",
            )

        if target_state == "learning" or source_state == "learning":
            self._stats["suggested"] += 1
            self._log_action(
                zone_id, module_id, actions, reason, context,
                result="would_have_executed", source_module=source_module,
            )
            return ExecutionResult(
                zone_id=zone_id, module_id=module_id,
                decision="suggested",
                reason=f"Module in learning (source={source_module}:{source_state}, target={module_id}:{target_state})",
                actions=actions,
            )

        # 3. Double-safety via module registry
        if self._module_registry:
            if not self._module_registry.should_auto_apply_zone(zone_id, source_module, module_id):
                self._stats["suggested"] += 1
                return ExecutionResult(
                    zone_id=zone_id, module_id=module_id,
                    decision="suggested",
                    reason="Double-safety: should_auto_apply_zone returned False",
                    actions=actions,
                )

        # 4. Rate limiting
        if self._is_rate_limited(zone_id, module_id):
            self._stats["skipped"] += 1
            return ExecutionResult(
                zone_id=zone_id, module_id=module_id,
                decision="skipped", reason="Rate limited (30s cooldown)",
            )

        # ── EXECUTE ─────────────────────────────────────────────────────
        errors = []
        executed_actions = []

        for action in actions:
            action_type = action.get("type", "")
            try:
                if action_type == "light.turn_on" and self._ha_bridge:
                    result = self._ha_bridge.turn_on_light(
                        entity_id=action["entity_id"],
                        brightness_pct=action.get("brightness_pct", 100),
                        color_temp_k=action.get("color_temp_k"),
                    )
                    if not result.ok:
                        errors.append(f"light error: {result.error}")
                    else:
                        executed_actions.append(action)

                elif action_type == "light.turn_off" and self._ha_bridge:
                    result = self._ha_bridge.turn_off_light(action["entity_id"])
                    if not result.ok:
                        errors.append(f"light off error: {result.error}")
                    else:
                        executed_actions.append(action)

                elif action_type == "music.play_favorite" and self._musikwolke_bridge:
                    room = action.get("room", "")
                    favorite = action.get("favorite", "")
                    volume = action.get("volume_pct")
                    if room and favorite:
                        # Use sonos client directly for favorites
                        sonos = getattr(self._musikwolke_bridge, "_sonos", None)
                        if sonos and hasattr(sonos, "play_favorite"):
                            sonos.play_favorite(room, favorite)
                            if volume is not None:
                                self._musikwolke_bridge.set_zone_volume(zone_id, volume)
                            executed_actions.append(action)

                elif action_type == "music.play" and self._musikwolke_bridge:
                    volume = action.get("volume_pct")
                    self._musikwolke_bridge.play_in_zone(zone_id, volume_pct=volume)
                    executed_actions.append(action)

                elif action_type == "music.pause" and self._musikwolke_bridge:
                    self._musikwolke_bridge.pause_in_zone(zone_id)
                    executed_actions.append(action)

                else:
                    _LOGGER.debug("Unknown action type: %s", action_type)

            except Exception as exc:
                errors.append(f"{action_type}: {exc}")
                _LOGGER.exception("Action execution failed: %s", action_type)

        self._record_execution(zone_id, module_id)

        if errors:
            self._stats["errors"] += 1
            error_str = "; ".join(errors)
        else:
            error_str = ""

        if executed_actions:
            self._stats["executed"] += 1
            self._log_action(
                zone_id, module_id, executed_actions, reason, context,
                result="ok" if not errors else "partial",
                source_module=source_module,
            )
            # Publish bus event
            if self._bus:
                try:
                    self._bus.publish("autonomy.executed", {
                        "zone_id": zone_id,
                        "module_id": module_id,
                        "actions": executed_actions,
                        "reason": reason,
                        "mood": context.get("mood", ""),
                        "confidence": context.get("confidence", 0),
                    }, source="autonomy_executor")
                except Exception:
                    _LOGGER.debug("Failed to publish autonomy.executed", exc_info=True)

            return ExecutionResult(
                zone_id=zone_id, module_id=module_id,
                decision="executed", reason=reason,
                actions=executed_actions, error=error_str,
            )

        self._stats["skipped"] += 1
        return ExecutionResult(
            zone_id=zone_id, module_id=module_id,
            decision="skipped", reason="No actions executed",
            error=error_str,
        )

    # ── Bus Event Handlers ──────────────────────────────────────────────

    def on_mood_changed(self, event) -> None:
        """Handle mood.changed bus events.

        Reads current mood, fetches weather context, and executes
        light/music actions for all occupied zones.
        """
        data = event.data if hasattr(event, "data") else {}
        mood = data.get("mood", data.get("dominant_mood", ""))
        confidence = data.get("confidence", data.get("mood_confidence", 0))

        if not mood:
            return

        # Weather context from NeuronManager
        weather_score = None
        weather_label = ""
        if self._neuron_manager:
            try:
                last_result = self._neuron_manager.get_last_result()
                if last_result and hasattr(last_result, "context_values"):
                    weather_score = last_result.context_values.get("weather", None)
                    if weather_score is not None:
                        weather_label = (
                            "sonnig" if weather_score > 0.7
                            else "bewoelkt" if weather_score > 0.3
                            else "regnerisch"
                        )
            except Exception:
                _LOGGER.debug("Failed to get weather context", exc_info=True)

        # Get mood actions
        mapper = self._get_mood_mapper()
        mood_actions = mapper.get_mood_actions(mood, weather_score=weather_score)

        context = {
            "mood": mood,
            "confidence": confidence,
            "weather": weather_label,
            "weather_score": weather_score,
            "trigger": "mood.changed",
        }

        # Execute for all zones
        if not self._zone_automation:
            return

        try:
            all_states = self._zone_automation.get_all_states()
        except Exception:
            _LOGGER.debug("Failed to get zone states", exc_info=True)
            return

        for zone_state in all_states:
            zone_id = zone_state.get("zone_id", "")
            if not zone_id:
                continue

            # Get zone entities by role
            try:
                entities_by_role = self._zone_automation.get_zone_entities_by_role(zone_id)
            except Exception:
                continue

            # Light actions
            lights = entities_by_role.get("lights", [])
            if lights and mood_actions.brightness_pct > 0:
                light_actions = []
                for light_entity in lights:
                    eid = light_entity.get("entity_id", "") if isinstance(light_entity, dict) else str(light_entity)
                    if eid:
                        light_actions.append({
                            "type": "light.turn_on",
                            "entity_id": eid,
                            "brightness_pct": mood_actions.brightness_pct,
                            "color_temp_k": mood_actions.color_temp_k,
                        })
                if light_actions:
                    self.execute_if_allowed(
                        zone_id, "licht", light_actions,
                        reason=f"Mood '{mood}' → Licht {mood_actions.brightness_pct}% ({mood_actions.color_temp_k}K)",
                        context=context, source_module="mood",
                    )
            elif lights and mood_actions.brightness_pct == 0:
                off_actions = []
                for light_entity in lights:
                    eid = light_entity.get("entity_id", "") if isinstance(light_entity, dict) else str(light_entity)
                    if eid:
                        off_actions.append({"type": "light.turn_off", "entity_id": eid})
                if off_actions:
                    self.execute_if_allowed(
                        zone_id, "licht", off_actions,
                        reason=f"Mood '{mood}' → Licht aus",
                        context=context, source_module="mood",
                    )

            # Music actions
            if mood_actions.music_action == "play" and mood_actions.music_favorite:
                # Resolve zone to Sonos room
                room = ""
                if self._musikwolke_bridge:
                    speaker_map = self._musikwolke_bridge.get_zone_speaker_map()
                    room = speaker_map.get(zone_id, zone_id.replace("_", " ").title())

                music_actions = [{
                    "type": "music.play_favorite",
                    "room": room,
                    "favorite": mood_actions.music_favorite,
                    "volume_pct": mood_actions.music_volume_pct,
                    "music_favorite": mood_actions.music_favorite,
                }]
                self.execute_if_allowed(
                    zone_id, "musik", music_actions,
                    reason=f"Mood '{mood}' → Musik '{mood_actions.music_favorite}'",
                    context=context, source_module="mood",
                )

            elif mood_actions.music_action == "pause":
                music_actions = [{"type": "music.pause"}]
                self.execute_if_allowed(
                    zone_id, "musik", music_actions,
                    reason=f"Mood '{mood}' → Musik Pause",
                    context=context, source_module="mood",
                )

    def on_presence_changed(self, event) -> None:
        """Handle presence.changed bus events.

        Delegates to ZoneAutomationController for presence-based actions,
        then executes light/music through governance pipeline.
        """
        data = event.data if hasattr(event, "data") else {}
        zone_id = data.get("zone_id", "")
        detected = data.get("detected", data.get("occupied", False))

        if not zone_id or not self._zone_automation:
            return

        context = {
            "trigger": "presence.changed",
            "detected": detected,
            "mood": "",
            "confidence": 0,
        }

        # Get current mood if available
        if self._neuron_manager:
            try:
                last_result = self._neuron_manager.get_last_result()
                if last_result:
                    context["mood"] = last_result.dominant_mood
                    context["confidence"] = last_result.mood_confidence
            except Exception:
                pass

        if detected:
            # Presence detected → use mood-based lighting if available
            mood = context.get("mood", "")
            if mood:
                mapper = self._get_mood_mapper()
                mood_actions = mapper.get_mood_actions(mood)

                try:
                    entities_by_role = self._zone_automation.get_zone_entities_by_role(zone_id)
                except Exception:
                    return

                # Light actions based on mood
                lights = entities_by_role.get("lights", [])
                if lights and mood_actions.brightness_pct > 0:
                    light_actions = []
                    for light_entity in lights:
                        eid = light_entity.get("entity_id", "") if isinstance(light_entity, dict) else str(light_entity)
                        if eid:
                            light_actions.append({
                                "type": "light.turn_on",
                                "entity_id": eid,
                                "brightness_pct": mood_actions.brightness_pct,
                                "color_temp_k": mood_actions.color_temp_k,
                            })
                    if light_actions:
                        self.execute_if_allowed(
                            zone_id, "licht", light_actions,
                            reason=f"Praesenz erkannt + Mood '{mood}'",
                            context=context, source_module="bewegung",
                        )
        else:
            # Presence cleared → turn off lights
            try:
                entities_by_role = self._zone_automation.get_zone_entities_by_role(zone_id)
            except Exception:
                return

            lights = entities_by_role.get("lights", [])
            if lights:
                off_actions = []
                for light_entity in lights:
                    eid = light_entity.get("entity_id", "") if isinstance(light_entity, dict) else str(light_entity)
                    if eid:
                        off_actions.append({"type": "light.turn_off", "entity_id": eid})
                if off_actions:
                    self.execute_if_allowed(
                        zone_id, "licht", off_actions,
                        reason="Praesenz verloren → Licht aus",
                        context=context, source_module="bewegung",
                    )

            # Pause music
            music_actions = [{"type": "music.pause"}]
            self.execute_if_allowed(
                zone_id, "musik", music_actions,
                reason="Praesenz verloren → Musik Pause",
                context=context, source_module="bewegung",
            )

    # ── Logging ─────────────────────────────────────────────────────────

    def _log_action(
        self,
        zone_id: str,
        module_id: str,
        actions: List[Dict[str, Any]],
        reason: str,
        context: Dict[str, Any],
        result: str = "ok",
        source_module: str = "mood",
    ) -> None:
        """Log action to behavioral log."""
        if not self._behavioral_log:
            return

        try:
            from copilot_core.autonomy.behavioral_log import ActionLogEntry

            # Flatten actions into details
            details = {}
            for action in actions:
                for k, v in action.items():
                    if k != "type":
                        details[k] = v

            entry = ActionLogEntry(
                zone_id=zone_id,
                module_id=module_id,
                action=actions[0].get("type", "") if actions else "",
                mood=context.get("mood", ""),
                confidence=context.get("confidence", 0),
                weather=context.get("weather", ""),
                trigger=context.get("trigger", ""),
                result=result,
                details=details,
            )
            self._behavioral_log.log_action(entry)
        except Exception:
            _LOGGER.debug("Failed to log action", exc_info=True)

    # ── Dashboard ───────────────────────────────────────────────────────

    def get_dashboard(self) -> Dict[str, Any]:
        """Return autonomy execution dashboard data."""
        zones = []
        if self._zone_automation:
            try:
                all_states = self._zone_automation.get_all_states()
                for zone_state in all_states:
                    zone_id = zone_state.get("zone_id", "")
                    zone_info = {
                        "zone_id": zone_id,
                        "automation_mode": zone_state.get("automation_mode", "off"),
                        "occupied": zone_state.get("occupied", False),
                    }
                    # Add per-zone module states
                    if self._module_registry:
                        zone_info["module_states"] = self._module_registry.get_zone_states(zone_id)
                    zones.append(zone_info)
            except Exception:
                _LOGGER.debug("Failed to build dashboard", exc_info=True)

        log_stats = {}
        if self._behavioral_log:
            try:
                log_stats = self._behavioral_log.get_stats()
            except Exception:
                pass

        return {
            "zones": zones,
            "stats": dict(self._stats),
            "log": log_stats,
            "rate_limit_seconds": _RATE_LIMIT_SECONDS,
        }
