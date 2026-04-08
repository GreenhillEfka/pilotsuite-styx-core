"""
Proactive Context Engine -- Non-intrusive contextual suggestions.

Generates smart suggestions when users move between zones, based on:
- Time of day
- Zone context (what media was playing, what devices are there)
- User preferences (from conversation memory + user profiles)
- Household context (who else is home, children present?)

Suggestions are delivered via TTS, notification, or chat --
configurable per user. The engine is intentionally NON-PENETRANT:
it respects cooldown periods, quiet hours, and user dismissals.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

_LOGGER = logging.getLogger(__name__)

SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")

# Cooldown: don't suggest again for the same zone within this many seconds
ZONE_COOLDOWN_SECONDS = int(os.environ.get("PROACTIVE_COOLDOWN", "1800"))  # 30 min

# Quiet hours: no proactive suggestions during these hours
QUIET_START = int(os.environ.get("QUIET_HOUR_START", "23"))
QUIET_END = int(os.environ.get("QUIET_HOUR_END", "7"))


class ProactiveContextEngine:
    """Generate context-aware suggestions on zone entry.

    Non-intrusive by design: respects cooldowns, quiet hours, user
    dismissals, and household context.  Suggestions are templates
    that can be delivered via TTS, persistent notification, or chat.
    """

    def __init__(self, media_zone_manager=None, mood_service=None,
                 household_profile=None, conversation_memory=None,
                 waste_service=None, birthday_service=None,
                 habitus_service=None):
        self._media_mgr = media_zone_manager
        self._mood_svc = mood_service
        self._household = household_profile
        self._conv_memory = conversation_memory
        self._waste_svc = waste_service
        self._birthday_svc = birthday_service
        self._habitus_svc = habitus_service
        self._lock = threading.Lock()
        # Track last suggestion time per (person, zone)
        self._cooldowns: Dict[str, float] = {}
        # Track dismissed suggestion types per person
        self._dismissed: Dict[str, set] = {}
        # Cooldown for presence triggers per person (prevent rapid-fire)
        self._presence_cooldowns: Dict[str, float] = {}
        _LOGGER.info("ProactiveContextEngine initialized")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def on_zone_entry(self, person_id: str, zone_id: str,
                      context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Generate suggestions when a person enters a zone.

        Parameters
        ----------
        person_id : str
            HA person entity (e.g. person.alice).
        zone_id : str
            Zone entered (e.g. living_room, kitchen).
        context : dict, optional
            Extra context (time, devices, media state, etc.).

        Returns
        -------
        list[dict]
            Suggestions with type, message, action, priority.
            Empty list if suppressed (cooldown, quiet hours, etc.).
        """
        # Check quiet hours
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        local_hour = (now.hour + int(os.environ.get("TZ_OFFSET", "1"))) % 24
        if QUIET_START <= 23 and (local_hour >= QUIET_START or local_hour < QUIET_END):
            return []

        # Check cooldown
        key = f"{person_id}:{zone_id}"
        with self._lock:
            last = self._cooldowns.get(key, 0)
            if time.time() - last < ZONE_COOLDOWN_SECONDS:
                return []
            self._cooldowns[key] = time.time()

        # Build context
        ctx = context or {}
        ctx.setdefault("person_id", person_id)
        ctx.setdefault("zone_id", zone_id)
        ctx.setdefault("hour", local_hour)
        ctx.setdefault("is_evening", 18 <= local_hour <= 23)
        ctx.setdefault("is_morning", 6 <= local_hour <= 10)

        # Get media state for zone
        if self._media_mgr:
            try:
                media_state = self._media_mgr.get_zone_media_state(zone_id)
                ctx["media_state"] = media_state
            except Exception:
                pass

        # Get mood for zone
        if self._mood_svc:
            try:
                mood = self._mood_svc.get_zone_mood(zone_id)
                ctx["mood"] = mood
            except Exception:
                pass

        # Get household context
        if self._household:
            try:
                ctx["household"] = self._household.to_dict()
                ctx["children_home"] = self._household.is_any_child_home()
            except Exception:
                pass

        # Generate suggestions
        suggestions = []
        suggestions.extend(self._media_suggestions(ctx))
        suggestions.extend(self._comfort_suggestions(ctx))
        suggestions.extend(self._routine_suggestions(ctx))

        # Filter dismissed types
        person_dismissed = self._dismissed.get(person_id, set())
        suggestions = [s for s in suggestions
                       if s.get("type") not in person_dismissed]

        return suggestions

    # ------------------------------------------------------------------
    # Suggestion generators
    # ------------------------------------------------------------------

    def _media_suggestions(self, ctx: dict) -> List[Dict[str, Any]]:
        """Suggest media actions based on zone + time context."""
        suggestions = []
        zone = ctx.get("zone_id", "")
        hour = ctx.get("hour", 12)
        media = ctx.get("media_state", {})
        person = ctx.get("person_id", "")

        # Evening + living room + no media playing → suggest TV/music
        if ctx.get("is_evening") and "wohnzimmer" in zone.lower() or "living" in zone.lower():
            if media.get("state") != "playing":
                suggestions.append({
                    "type": "media_suggest",
                    "priority": "low",
                    "message": f"Du bist im Wohnzimmer. Soll ich Netflix auf dem Apple TV starten?",
                    "message_en": f"You're in the living room. Want me to start Netflix on Apple TV?",
                    "action": {
                        "service": "media_player.select_source",
                        "data": {"source": "Netflix"},
                    },
                    "zone_id": zone,
                    "dismissible": True,
                })

        # Music was playing in another zone → offer Musikwolke
        if self._media_mgr:
            sessions = self._media_mgr.get_musikwolke_sessions()
            for s in sessions:
                if s.get("person_id") == person and zone not in s.get("active_zones", []):
                    suggestions.append({
                        "type": "musikwolke_extend",
                        "priority": "low",
                        "message": f"Deine Musik laeuft noch. Soll ich sie hierher mitnehmen?",
                        "message_en": "Your music is still playing. Want me to bring it here?",
                        "action": {
                            "musikwolke_session": s.get("session_id"),
                            "extend_to_zone": zone,
                        },
                        "zone_id": zone,
                        "dismissible": True,
                    })

        return suggestions

    def _comfort_suggestions(self, ctx: dict) -> List[Dict[str, Any]]:
        """Suggest comfort adjustments."""
        suggestions = []
        zone = ctx.get("zone_id", "")
        mood = ctx.get("mood", {})

        # Low comfort score → suggest adjustment
        if mood.get("comfort", 0.5) < 0.3:
            suggestions.append({
                "type": "comfort_adjust",
                "priority": "medium",
                "message": "Der Komfort in diesem Raum ist niedrig. Soll ich die Beleuchtung anpassen?",
                "action": {"service": "light.turn_on",
                           "data": {"brightness_pct": 60}},
                "zone_id": zone,
                "dismissible": True,
            })

        return suggestions

    def _routine_suggestions(self, ctx: dict) -> List[Dict[str, Any]]:
        """Suggest based on known routines / time patterns."""
        suggestions = []
        zone = ctx.get("zone_id", "")
        hour = ctx.get("hour", 12)

        # Morning + kitchen → suggest coffee / morning routine
        if ctx.get("is_morning") and ("kueche" in zone.lower() or "kitchen" in zone.lower()):
            suggestions.append({
                "type": "morning_routine",
                "priority": "low",
                "message": "Guten Morgen! Soll ich die Morgenroutine starten?",
                "action": {"scene": "scene.morning_routine"},
                "zone_id": zone,
                "dismissible": True,
            })

        return suggestions

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def deliver_suggestion(self, suggestion: dict,
                           method: str = "notification") -> dict:
        """Deliver a suggestion to the user.

        Methods: 'notification' (persistent), 'tts', 'chat'.
        """
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return {"ok": False, "error": "No SUPERVISOR_TOKEN"}

        headers = {"Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"}
        message = suggestion.get("message", "")

        if method == "tts":
            # Use TTS service
            zone = suggestion.get("zone_id", "")
            # Get media players in zone for TTS target
            tts_entity = None
            if self._media_mgr:
                players = self._media_mgr.get_zone_players(zone)
                if players:
                    tts_entity = players[0]["entity_id"]
            if tts_entity:
                try:
                    requests.post(
                        f"{SUPERVISOR_API}/services/tts/speak",
                        json={"entity_id": tts_entity,
                              "message": message,
                              "cache": True},
                        headers=headers, timeout=10,
                    )
                    return {"ok": True, "method": "tts", "entity": tts_entity}
                except Exception as exc:
                    _LOGGER.warning("TTS delivery failed: %s", exc)

        # Fallback: persistent notification
        try:
            requests.post(
                f"{SUPERVISOR_API}/services/notify/persistent_notification",
                json={"message": message, "title": "Styx"},
                headers=headers, timeout=10,
            )
            return {"ok": True, "method": "notification"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # User feedback
    # ------------------------------------------------------------------

    def dismiss_type(self, person_id: str, suggestion_type: str) -> None:
        """User dismisses a suggestion type -- don't show again."""
        self._dismissed.setdefault(person_id, set()).add(suggestion_type)
        _LOGGER.info("Person %s dismissed suggestion type: %s",
                      person_id, suggestion_type)

    def reset_dismissals(self, person_id: str) -> None:
        """Reset all dismissals for a person."""
        self._dismissed.pop(person_id, None)

    # ------------------------------------------------------------------
    # Presence-based triggers  (v3.2.3)
    # ------------------------------------------------------------------

    # Cooldown between presence triggers for the same person (seconds)
    PRESENCE_COOLDOWN_SECONDS = 300  # 5 min

    def check_presence_triggers(
        self, presence_data: dict
    ) -> List[Dict[str, Any]]:
        """Generate contextual suggestions from presence changes.

        Parameters
        ----------
        presence_data : dict
            Expected format::

                {
                    "persons_home": ["person.alice", "person.bob"],
                    "persons_away": ["person.charlie"],
                    "total_home": 2,
                    "last_event": {
                        "person_id": "person.alice",
                        "event": "arrive",       # "arrive" | "leave"
                        "timestamp": 1708345600,  # optional epoch
                    }
                }

        Returns
        -------
        list[dict]
            Each suggestion::

                {
                    "type": "greeting" | "eco_mode" | "pattern",
                    "message": str,
                    "priority": float,   # 0.0 .. 1.0
                    "person": str | None
                }
        """
        suggestions: List[Dict[str, Any]] = []
        last_event = presence_data.get("last_event") or {}
        person_id = last_event.get("person_id", "")
        event_type = last_event.get("event", "")
        total_home = presence_data.get("total_home", 0)

        # --- Quiet-hours gate ------------------------------------------------
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        local_hour = (now.hour + int(os.environ.get("TZ_OFFSET", "1"))) % 24
        if QUIET_START <= 23 and (local_hour >= QUIET_START or local_hour < QUIET_END):
            return []

        # --- Per-person cooldown ---------------------------------------------
        if person_id:
            with self._lock:
                last_ts = self._presence_cooldowns.get(person_id, 0)
                if time.time() - last_ts < self.PRESENCE_COOLDOWN_SECONDS:
                    _LOGGER.debug(
                        "Presence cooldown active for %s -- skipping",
                        person_id,
                    )
                    return []
                self._presence_cooldowns[person_id] = time.time()

        # --- 1. Arrival Greeting ---------------------------------------------
        if event_type == "arrive" and person_id:
            greeting = self._build_arrival_greeting(person_id, local_hour)
            if greeting:
                suggestions.append(greeting)

        # --- 2. All-Away / Eco-Mode ------------------------------------------
        if event_type == "leave" and total_home == 0:
            eco = self._build_eco_mode_suggestion(person_id)
            if eco:
                suggestions.append(eco)

        # --- 3. Pattern-based suggestions ------------------------------------
        pattern_suggestions = self._build_pattern_suggestions(presence_data)
        suggestions.extend(pattern_suggestions)

        # --- Filter dismissed types ------------------------------------------
        if person_id:
            person_dismissed = self._dismissed.get(person_id, set())
            suggestions = [
                s for s in suggestions
                if s.get("type") not in person_dismissed
            ]

        return suggestions

    # ------------------------------------------------------------------
    # Presence helpers
    # ------------------------------------------------------------------

    def _build_arrival_greeting(
        self, person_id: str, local_hour: int
    ) -> Optional[Dict[str, Any]]:
        """Build a personalised arrival greeting with household context.

        Returns a suggestion dict or ``None`` if nothing useful to say.
        """
        # Resolve display name from household profile
        name = person_id
        if self._household:
            try:
                member = self._household.get_member(person_id)
                if member:
                    name = member.name
            except Exception:
                pass

        # Gather contextual nuggets
        context_parts: List[str] = []

        # Waste collection today?
        if self._waste_svc:
            try:
                status = self._waste_svc.get_status()
                today_waste = status.get("today", [])
                if today_waste:
                    types_str = ", ".join(today_waste)
                    context_parts.append(f"Heute ist Muellabfuhr ({types_str}).")
            except Exception:
                pass

        # Birthday today?
        if self._birthday_svc:
            try:
                bday_status = self._birthday_svc.get_status()
                today_bdays = bday_status.get("today", [])
                for bday in today_bdays:
                    bday_name = bday.get("name", "jemand")
                    context_parts.append(f"{bday_name} hat heute Geburtstag!")
            except Exception:
                pass

        # Time-of-day flavour
        if 6 <= local_hour <= 10:
            greeting_prefix = "Guten Morgen"
        elif 18 <= local_hour <= 22:
            greeting_prefix = "Guten Abend"
        else:
            greeting_prefix = "Willkommen zuhause"

        context_str = " ".join(context_parts) if context_parts else ""
        if context_str:
            message = f"{greeting_prefix}, {name}! {context_str}"
        else:
            message = f"{greeting_prefix}, {name}!"

        return {
            "type": "greeting",
            "message": message,
            "priority": 0.7,
            "person": person_id,
        }

    def _build_eco_mode_suggestion(
        self, last_person_id: str
    ) -> Dict[str, Any]:
        """Build an eco-mode suggestion when the last person leaves."""
        return {
            "type": "eco_mode",
            "message": (
                "Alle haben das Haus verlassen. "
                "Soll ich den Sparmodus aktivieren?"
            ),
            "priority": 0.9,
            "person": last_person_id or None,
        }

    def _build_pattern_suggestions(
        self, presence_data: dict
    ) -> List[Dict[str, Any]]:
        """Check habitus miner rules and generate pattern-based suggestions.

        Looks for rules whose antecedent matches a presence-related event
        (e.g. ``person.alice:home``) and returns the consequent as a
        suggested action.
        """
        suggestions: List[Dict[str, Any]] = []

        if not self._habitus_svc:
            return suggestions

        last_event = presence_data.get("last_event") or {}
        person_id = last_event.get("person_id", "")
        event_type = last_event.get("event", "")

        if not person_id or not event_type:
            return suggestions

        # Build the antecedent key that habitus_miner would have recorded
        # for this presence transition (e.g. "person.alice:home")
        transition = "home" if event_type == "arrive" else "not_home"
        search_key = f"{person_id}:{transition}"

        try:
            # Try the HabitusMinerService (habitus_miner/) first -- it
            # stores Rule objects with .A / .B keys.
            rules = []
            if hasattr(self._habitus_svc, "get_rules"):
                rules = self._habitus_svc.get_rules(
                    a_filter=search_key, limit=5
                )
            elif hasattr(self._habitus_svc, "list_recent_patterns"):
                # Fallback: HabitusService (habitus/) stores patterns
                # in candidate form.
                patterns = self._habitus_svc.list_recent_patterns(limit=20)
                for p in patterns:
                    meta = p.get("metadata", {})
                    antecedent = meta.get("antecedent", {}).get("full", "")
                    if search_key.lower() in antecedent.lower():
                        consequent = meta.get("consequent", {})
                        evidence = p.get("evidence", {})
                        confidence = 0.0
                        if isinstance(evidence, dict):
                            confidence = evidence.get("confidence", 0.0)
                        suggestions.append({
                            "type": "pattern",
                            "message": (
                                f"Erkanntes Muster: Wenn du {event_type == 'arrive' and 'ankommst' or 'gehst'}, "
                                f"wird normalerweise {consequent.get('full', consequent.get('service', '?'))} "
                                f"ausgefuehrt. Soll ich das uebernehmen?"
                            ),
                            "priority": round(min(1.0, confidence * 0.8), 2),
                            "person": person_id,
                        })
                return suggestions

            # Process Rule objects (from HabitusMinerService)
            for rule in rules:
                score = rule.score() if hasattr(rule, "score") else 0.5
                suggestions.append({
                    "type": "pattern",
                    "message": (
                        f"Erkanntes Muster: Nach deiner Ankunft wird oft "
                        f"{rule.B} ausgefuehrt "
                        f"(Konfidenz {rule.confidence:.0%}). "
                        f"Soll ich das uebernehmen?"
                    ),
                    "priority": round(min(1.0, score), 2),
                    "person": person_id,
                })

        except Exception as exc:
            _LOGGER.warning("Pattern lookup for presence trigger failed: %s", exc)

        return suggestions

    # ------------------------------------------------------------------
    # REST endpoint helper  (v3.2.3)
    # ------------------------------------------------------------------

    def build_presence_endpoint_response(
        self, presence_data: dict
    ) -> Dict[str, Any]:
        """Convenience wrapper for REST endpoint integration.

        Call this from a Flask route handler (e.g. in *presence.py*)::

            @bp.post("/presence/trigger")
            def presence_trigger():
                data = request.get_json(silent=True) or {}
                return jsonify(engine.build_presence_endpoint_response(data))

        Returns a dict ready for ``jsonify()``.
        """
        try:
            suggestions = self.check_presence_triggers(presence_data)
            return {
                "ok": True,
                "total_home": presence_data.get("total_home", 0),
                "last_event": presence_data.get("last_event"),
                "suggestions": suggestions,
                "suggestion_count": len(suggestions),
            }
        except Exception as exc:
            _LOGGER.exception("Presence trigger processing failed")
            return {
                "ok": False,
                "error": str(exc),
                "suggestions": [],
                "suggestion_count": 0,
            }
