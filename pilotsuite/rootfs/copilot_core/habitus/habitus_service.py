"""Habitus Service — High-Level API für Life-Long-Learning.

Diese Service-Schicht vereinfacht die Nutzung von HabitusStorage:
- Auto-Confidence-Berechnung
- Pattern-Matching (Trigger → Action)
- Cross-Module-Learning
- Smart Feedback-Verarbeitung
- Proaktive Vorschläge

Usage:
    service = HabitusService()
    
    # Pattern beobachten
    service.observe(trigger={"time": "19:30", "presence": True}, action={"module": "light", "command": "on"})
    
    # Vorschläge generieren
    proposals = service.get_proposals(zone="living")
    
    # Feedback verarbeiten
    service.process_feedback(pattern_id="p1", feedback_type="accepted")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from .habitus_storage import (
    get_habitus_storage,
    HabitusStorage,
    Pattern,
    PatternState,
    UserPreference,
    UserRoutine,
    UserFeedback,
    FeedbackType,
    ContextHistory,
)

_LOGGER = logging.getLogger(__name__)


class HabitusService:
    """High-Level Service für Habitus-Learning.
    
    Bietet intelligente Abstraktionen über HabitusStorage:
    - Automatische Pattern-Erkennung
    - Confidence-Berechnung mit Wilson Score
    - Cross-Module Synergien
    - Proaktive Vorschläge
    """
    
    def __init__(self, storage: Optional[HabitusStorage] = None):
        self._storage = storage or get_habitus_storage()
        _LOGGER.info("HabitusService initialized")
    
    # ======================================================================
    # Pattern Observation & Learning
    # ======================================================================
    
    def observe(
        self,
        trigger: Dict[str, Any],
        action: Dict[str, Any],
        zone: Optional[str] = None,
        module: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Eine Aktion beobachten und Pattern anlegen/updaten.
        
        Args:
            trigger: Auslöser (time, presence, zone, etc.)
            action: Ausgeführte Aktion (module, command)
            zone: Optional Zone
            module: Optional Modul
            context: Optional zusätzlicher Kontext
        
        Returns:
            Pattern-ID
        """
        # Existierendes Pattern finden (ähnlicher Trigger + Action)
        existing = self._find_matching_pattern(trigger, action)
        
        if existing:
            # Pattern updaten (support++, last_learned)
            existing.support += 1
            existing.last_learned = datetime.now(timezone.utc).isoformat()
            
            if zone and zone not in existing.zones:
                existing.zones.append(zone)
            if module and module not in existing.modules:
                existing.modules.append(module)
            
            # Confidence neu berechnen
            existing.update_confidence()
            
            self._storage.save_pattern(existing)
            _LOGGER.info(f"Pattern updated: {existing.id} (support={existing.support})")
            
            return existing.id
        else:
            # Neues Pattern anlegen
            pattern = Pattern(
                id=f"p_{uuid.uuid4().hex[:8]}",
                description=self._generate_description(trigger, action),
                trigger=trigger,
                action=action,
                support=1,
                zones=[zone] if zone else [],
                modules=[module] if module else [],
                contexts=[context] if context else [],
                state=PatternState.OBSERVING,
            )
            
            self._storage.save_pattern(pattern)
            _LOGGER.info(f"New pattern created: {pattern.id}")
            
            return pattern.id
    
    def _find_matching_pattern(
        self,
        trigger: Dict[str, Any],
        action: Dict[str, Any],
        similarity_threshold: float = 0.8,
    ) -> Optional[Pattern]:
        """Existierendes Pattern mit ähnlichem Trigger+Action finden."""
        all_patterns = self._storage.get_patterns()
        
        for pattern in all_patterns:
            # Trigger-Vergleich
            trigger_match = self._compare_triggers(pattern.trigger, trigger)
            action_match = self._compare_actions(pattern.action, action)
            
            if trigger_match >= similarity_threshold and action_match >= similarity_threshold:
                return pattern
        
        return None
    
    def _compare_triggers(self, t1: Dict[str, Any], t2: Dict[str, Any]) -> float:
        """Trigger-Ähnlichkeit berechnen (0.0-1.0)."""
        if not t1 or not t2:
            return 0.0
        
        common_keys = set(t1.keys()) & set(t2.keys())
        if not common_keys:
            return 0.0
        
        matches = sum(1 for k in common_keys if t1.get(k) == t2.get(k))
        return matches / len(common_keys)
    
    def _compare_actions(self, a1: Dict[str, Any], a2: Dict[str, Any]) -> float:
        """Action-Ähnlichkeit berechnen (0.0-1.0)."""
        if not a1 or not a2:
            return 0.0
        
        # Module muss matchen
        if a1.get("module") != a2.get("module"):
            return 0.0
        
        # Command kann ähnlich sein (on ≈ turn_on)
        cmd1 = a1.get("command", "")
        cmd2 = a2.get("command", "")
        
        if cmd1 == cmd2:
            return 1.0
        
        # Alias-Checking
        aliases = {
            "on": ["turn_on", "activate", "enable"],
            "off": ["turn_off", "deactivate", "disable"],
        }
        
        for base, alias_list in aliases.items():
            if (cmd1 == base and cmd2 in alias_list) or (cmd2 == base and cmd1 in alias_list):
                return 0.9
        
        return 0.5
    
    def _generate_description(self, trigger: Dict[str, Any], action: Dict[str, Any]) -> str:
        """Menschenlesbare Pattern-Beschreibung generieren."""
        parts = []
        
        # Trigger
        if "time" in trigger:
            parts.append(f"um {trigger['time']}")
        if "presence" in trigger and trigger["presence"]:
            parts.append("bei Präsenz")
        if "zone" in trigger:
            parts.append(f"in {trigger['zone']}")
        
        # Action
        module = action.get("module", "unknown")
        command = action.get("command", "unknown")
        
        action_map = {
            ("light", "turn_on"): "Licht einschalten",
            ("light", "turn_off"): "Licht ausschalten",
            ("light", "set_brightness"): "Helligkeit einstellen",
            ("climate", "set_temperature"): "Temperatur einstellen",
            ("climate", "turn_on"): "Heizung aktivieren",
            ("music", "play"): "Musik starten",
            ("music", "stop"): "Musik stoppen",
        }
        
        action_desc = action_map.get((module, command), f"{module}: {command}")
        
        return f"Wenn {' '.join(parts)}, dann {action_desc}."
    
    # ======================================================================
    # Proposals & Recommendations
    # ======================================================================
    
    def get_proposals(
        self,
        zone: Optional[str] = None,
        min_confidence: float = 0.7,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Vorschläge für den Nutzer generieren.
        
        Returns Patterns die bereit für Vorschlag sind (state=stable).
        """
        patterns = self._storage.get_patterns(
            zone=zone,
            state=PatternState.STABLE,
            min_confidence=min_confidence,
        )
        
        # Noch nicht vorgeschlagene Patterns priorisieren
        proposals = []
        for p in patterns[:limit]:
            if p.acceptances == 0 and p.rejections == 0:
                # Noch nie vorgeschlagen → hohe Priorität
                priority = 1.0
            else:
                # Bereits vorgeschlagen → basierend auf Akzeptanz
                priority = p.acceptances / max(p.acceptances + p.rejections, 1)
            
            proposals.append({
                "pattern_id": p.id,
                "description": p.description,
                "trigger": p.trigger,
                "action": p.action,
                "confidence": round(p.confidence * 100, 1),
                "priority": round(priority, 2),
                "zones": p.zones,
                "modules": p.modules,
            })
        
        # Nach Priorität sortieren
        proposals.sort(key=lambda x: x["priority"], reverse=True)
        
        return proposals
    
    def should_auto_apply(
        self,
        pattern_id: str,
        current_context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Prüfen ob Pattern automatisch angewendet werden soll.
        
        Returns:
            (should_apply, reason)
        """
        pattern = self._storage.get_pattern(pattern_id)
        
        if not pattern:
            return False, "Pattern not found"
        
        if pattern.state != PatternState.ACTIVE:
            return False, f"Pattern state is {pattern.state.value}, not active"
        
        if pattern.confidence < 0.8:
            return False, f"Confidence {pattern.confidence:.2f} < 0.8"
        
        if pattern.rejections > pattern.acceptances:
            return False, "More rejections than acceptances"
        
        # Trigger-Match prüfen
        trigger_match = self._check_trigger_match(pattern.trigger, current_context)
        if not trigger_match:
            return False, "Trigger does not match current context"
        
        return True, "All checks passed"
    
    def _check_trigger_match(
        self,
        trigger: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """Prüfen ob aktueller Kontext Trigger erfüllt."""
        for key, expected_value in trigger.items():
            actual_value = context.get(key)
            
            if key == "time":
                # Zeit-Fenster prüfen (±15 Minuten)
                if not self._time_in_window(expected_value, actual_value):
                    return False
            elif key == "presence":
                if actual_value != expected_value:
                    return False
            elif key == "zone":
                if actual_value != expected_value:
                    return False
            else:
                if actual_value != expected_value:
                    return False
        
        return True
    
    def _time_in_window(self, expected: str, actual: str, window_minutes: int = 15) -> bool:
        """Prüfen ob Zeit im Fenster liegt (±window_minutes)."""
        try:
            exp_hour, exp_min = map(int, expected.split(":"))
            act_hour, act_min = map(int, actual.split(":"))
            
            exp_total = exp_hour * 60 + exp_min
            act_total = act_hour * 60 + act_min
            
            diff = abs(exp_total - act_total)
            
            # Über Mitternacht handling
            if diff > 720:  # 12 Stunden
                diff = 1440 - diff
            
            return diff <= window_minutes
        except Exception:
            return False
    
    # ======================================================================
    # Feedback Processing
    # ======================================================================
    
    def process_feedback(
        self,
        pattern_id: str,
        feedback_type: str,
        comment: Optional[str] = None,
        correction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Feedback verarbeiten und Pattern anpassen.
        
        Args:
            pattern_id: Pattern-ID
            feedback_type: accepted, rejected, ignored, corrected
            comment: Optional Nutzer-Kommentar
            correction: Optional Korrektur-Vorschlag
        
        Returns:
            Result mit Pattern-Update-Info
        """
        pattern = self._storage.get_pattern(pattern_id)
        
        if not pattern:
            return {"success": False, "error": "Pattern not found"}
        
        # Feedback speichern
        feedback = UserFeedback(
            id=f"fb_{uuid.uuid4().hex[:8]}",
            pattern_id=pattern_id,
            feedback_type=FeedbackType(feedback_type),
            comment=comment,
            correction=correction,
        )
        
        self._storage.add_feedback(feedback)
        
        # Pattern anpassen
        if feedback_type == "accepted":
            pattern.confidence = min(pattern.confidence + 0.05, 1.0)
            if pattern.state == PatternState.STABLE and pattern.acceptances >= 5:
                pattern.state = PatternState.ACTIVE
        elif feedback_type == "rejected":
            pattern.confidence = max(pattern.confidence - 0.1, 0.0)
            if pattern.confidence < 0.5:
                pattern.state = PatternState.LEARNING
        elif feedback_type == "corrected":
            pattern.confidence = max(pattern.confidence - 0.05, 0.0)
            if correction:
                # Pattern korrigieren
                if "trigger" in correction:
                    pattern.trigger.update(correction["trigger"])
                if "action" in correction:
                    pattern.action.update(correction["action"])
        
        pattern.last_learned = datetime.now(timezone.utc).isoformat()
        self._storage.save_pattern(pattern)
        
        _LOGGER.info(f"Feedback processed for {pattern_id}: {feedback_type}")
        
        return {
            "success": True,
            "pattern_id": pattern_id,
            "new_confidence": round(pattern.confidence, 2),
            "new_state": pattern.state.value,
        }
    
    # ======================================================================
    # Preferences & Routines
    # ======================================================================
    
    def learn_preference(
        self,
        category: str,
        key: str,
        value: Any,
        zone: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        """Nutzer-Präferenz lernen.
        
        Example:
            learn_preference("light", "brightness", 40, zone="living", context="evening")
        """
        pref = UserPreference(
            category=category,
            key=key,
            value=value,
            zone=zone,
            context=context,
            confidence=0.5,  # Start confidence
            observations=1,
        )
        
        # Existierende Preference updaten
        existing = self._storage.get_preferences(category=category, zone=zone)
        for p in existing:
            if p.key == key and p.context == context:
                # Update existierende
                p.value = value
                p.observations += 1
                p.confidence = min(p.confidence + 0.1, 1.0)
                self._storage.save_preference(p)
                _LOGGER.info(f"Preference updated: {category}.{key} = {value}")
                return
        
        # Neue Preference
        self._storage.save_preference(pref)
        _LOGGER.info(f"New preference learned: {category}.{key} = {value}")
    
    def get_preference(
        self,
        category: str,
        key: str,
        zone: Optional[str] = None,
        context: Optional[str] = None,
        default: Any = None,
    ) -> Any:
        """Nutzer-Präferenz abrufen.
        
        Returns:
            Präferenz-Wert oder Default
        """
        prefs = self._storage.get_preferences(category=category, zone=zone)
        
        for p in prefs:
            if p.key == key:
                if context and p.context == context:
                    return p.value
                elif not context:
                    return p.value
        
        return default
    
    # ======================================================================
    # Analytics & Insights
    # ======================================================================
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Lern-Einblicke für den Nutzer.
        
        Returns:
            Insights mit Empfehlungen
        """
        stats = self._storage.get_stats()
        
        insights = []
        
        # Insight 1: Aktive Patterns
        active_count = stats.get("patterns_by_state", {}).get("active", 0)
        if active_count >= 10:
            insights.append({
                "type": "success",
                "title": "Gut gemacht!",
                "message": f"Du hast {active_count} aktive Automatisierungen.",
            })
        
        # Insight 2: Niedrige Akzeptanz-Rate
        feedback = stats.get("feedback_by_type", {})
        total_feedback = sum(feedback.values())
        if total_feedback > 10:
            acceptance_rate = feedback.get("accepted", 0) / total_feedback
            if acceptance_rate < 0.5:
                insights.append({
                    "type": "warning",
                    "title": "Verbesserungspotenzial",
                    "message": "Deine Akzeptanz-Rate ist niedrig. Vielleicht sind die Vorschläge nicht relevant genug?",
                })
        
        # Insight 3: Keine Routinen gelernt
        routines_count = stats.get("routines_total", 0)
        if routines_count == 0:
            insights.append({
                "type": "info",
                "title": "Tipp",
                "message": "Das System kann deine Routinen lernen. Führe Aktionen regelmäßig zur gleichen Zeit aus.",
            })
        
        return {
            "stats": stats,
            "insights": insights,
            "intelligence_score": self._calculate_intelligence_score(stats),
        }
    
    def _calculate_intelligence_score(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligence Score berechnen (0-100)."""
        total_patterns = stats.get("patterns_total", 0)
        active_patterns = stats.get("patterns_by_state", {}).get("active", 0)
        
        feedback = stats.get("feedback_by_type", {})
        total_feedback = sum(feedback.values())
        acceptances = feedback.get("accepted", 0)
        
        pattern_score = min(total_patterns * 2, 40)
        active_score = min(active_patterns * 5, 30)
        acceptance_score = min((acceptances / max(total_feedback, 1)) * 30, 30)
        
        total_score = pattern_score + active_score + acceptance_score
        
        level = "Novice"
        if total_score >= 80:
            level = "Expert"
        elif total_score >= 60:
            level = "Advanced"
        elif total_score >= 40:
            level = "Intermediate"
        elif total_score >= 20:
            level = "Beginner"
        
        return {
            "total": round(total_score, 1),
            "max": 100,
            "level": level,
            "breakdown": {
                "patterns_learned": round(pattern_score, 1),
                "active_automations": round(active_score, 1),
                "user_acceptance": round(acceptance_score, 1),
            },
        }


# =============================================================================
# Singleton
# =============================================================================

_service_instance: Optional[HabitusService] = None


def get_habitus_service() -> HabitusService:
    """Singleton-Zugriff auf HabitusService."""
    global _service_instance
    
    if _service_instance is None:
        _service_instance = HabitusService()
    
    return _service_instance
