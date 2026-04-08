"""Voice Context Integration for HA Assist.

Provides mood-based context for voice assistants:
- Current mood state
- Mood confidence
- Zone context
- Activity suggestions

HA 2025.8+ supports context-based sensor selection for Assist.
This module exposes the neural system state for voice commands.

See: Perplexity audit 2026-02-15 - Voice Assistant Integration
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class VoiceContext:
    """Voice context for HA Assist integration."""
    
    # Mood state
    dominant_mood: str = "unknown"
    mood_confidence: float = 0.0
    mood_contributors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zone context
    current_zone: str = "unknown"
    zone_presence: List[str] = field(default_factory=list)
    
    # Activity context
    active_devices: List[str] = field(default_factory=list)
    recent_actions: List[str] = field(default_factory=list)
    
    # Suggestions
    voice_suggestions: List[str] = field(default_factory=list)
    
    # Metadata
    last_update: str = ""
    context_version: str = "1.0"


class VoiceContextProvider:
    """Provides voice context from neural system state.
    
    Integration points:
    1. HA Assist Pipeline - Use mood context for response personalization
    2. Voice Response Templates - Mood-based phrasing
    3. Proactive Suggestions - "Would you like me to..."
    
    Usage in HA Automations:
    ```yaml
    automation:
      - alias: "Voice Context Update"
        trigger:
          - platform: state
            entity_id: sensor.ai_copilot_mood
        action:
          - service: pilotsuite.update_voice_context
    ```
    """
    
    # Mood to voice tone mapping
    MOOD_TONES = {
        "relax": {
            "tone": "calm",
            "greeting": "Entspannt",
            "suggestion_prefix": "Wenn du möchtest, könnte ich",
        },
        "focus": {
            "tone": "focused",
            "greeting": "Fokussiert",
            "suggestion_prefix": "Passt auf, ich könnte",
        },
        "active": {
            "tone": "energetic",
            "greeting": "Bereit",
            "suggestion_prefix": "Lass uns",
        },
        "sleep": {
            "tone": "quiet",
            "greeting": "Gute Nacht",
            "suggestion_prefix": "Soll ich beim Aufwachen",
        },
        "away": {
            "tone": "standby",
            "greeting": "Abwesend",
            "suggestion_prefix": "Bei Rückkehr könnte ich",
        },
        "alert": {
            "tone": "urgent",
            "greeting": "Achtung",
            "suggestion_prefix": "Wichtig:",
        },
        "social": {
            "tone": "friendly",
            "greeting": "Gesellig",
            "suggestion_prefix": "Vielleicht möchtest du",
        },
        "recovery": {
            "tone": "gentle",
            "greeting": "Erholung",
            "suggestion_prefix": "Ich könnte dir helfen",
        },
    }
    
    # Zone-based context
    ZONE_CONTEXTS = {
        "wohnzimmer": {
            "aliases": ["wohnzimmer", "wohn", " lounge"],
            "default_action": "Licht anpassen",
        },
        "schlafzimmer": {
            "aliases": ["schlafzimmer", "schlaf", "bett"],
            "default_action": "Licht dimmen",
        },
        "kueche": {
            "aliases": ["küche", "koch", "kochbereich"],
            "default_action": "Küchenlicht",
        },
        "buero": {
            "aliases": ["büro", "arbeit", "homeoffice"],
            "default_action": "Arbeitslicht",
        },
        "bad": {
            "aliases": ["bad", "badezimmer"],
            "default_action": "Befinden anpassen",
        },
    }
    
    def __init__(self):
        self._context = VoiceContext()
        self._last_mood: str = "unknown"
        self._mood_history: List[Dict[str, Any]] = []
        self._max_history = 20
    
    def update_from_neural_state(
        self,
        mood_data: Dict[str, Any],
        zone_data: Optional[Dict[str, Any]] = None,
        suggestion_data: Optional[List[Dict[str, Any]]] = None,
    ) -> VoiceContext:
        """Update voice context from neural system state.
        
        Args:
            mood_data: Output from MoodNeurons or mood sensor
            zone_data: Current zone presence info
            suggestion_data: Active suggestions from neural system
            
        Returns:
            Updated VoiceContext
        """
        now = datetime.now(timezone.utc)
        
        # Update mood
        self._context.dominant_mood = mood_data.get("mood", "unknown")
        self._context.mood_confidence = mood_data.get("confidence", 0.0)
        self._context.mood_contributors = mood_data.get("contributors", [])
        
        # Track mood history
        if self._context.dominant_mood != self._last_mood:
            self._mood_history.append({
                "mood": self._context.dominant_mood,
                "confidence": self._context.mood_confidence,
                "time": now.isoformat(),
            })
            self._mood_history = self._mood_history[-self._max_history:]
            self._last_mood = self._context.dominant_mood
        
        # Update zone
        if zone_data:
            self._context.current_zone = zone_data.get("current_zone", "unknown")
            self._context.zone_presence = zone_data.get("presence", [])
        
        # Generate voice suggestions
        self._context.voice_suggestions = self._generate_voice_suggestions(
            suggestion_data or []
        )
        
        # Update metadata
        self._context.last_update = now.isoformat()
        
        return self._context
    
    def _generate_voice_suggestions(
        self,
        suggestions: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate voice-friendly suggestions.
        
        Converts technical suggestions into natural language.
        """
        voice_suggestions = []
        
        mood_tone = self.MOOD_TONES.get(
            self._context.dominant_mood,
            self.MOOD_TONES["relax"]
        )
        
        for suggestion in suggestions[:3]:  # Limit to 3
            action = suggestion.get("action", "")
            confidence = suggestion.get("confidence", 0.0)
            
            if confidence < 0.5:
                continue
            
            # Convert action to voice-friendly format
            voice_action = self._action_to_voice(action, mood_tone)
            if voice_action:
                voice_suggestions.append(voice_action)
        
        return voice_suggestions
    
    def _action_to_voice(
        self,
        action: str,
        mood_tone: Dict[str, Any],
    ) -> str:
        """Convert technical action to voice-friendly phrase."""
        # Common action patterns
        action_lower = action.lower()
        
        # Light actions
        if "light" in action_lower or "licht" in action_lower:
            if "on" in action_lower or "an" in action_lower:
                return f"{mood_tone['suggestion_prefix']} das Licht einschalten"
            elif "off" in action_lower or "aus" in action_lower:
                return f"{mood_tone['suggestion_prefix']} das Licht ausschalten"
            elif "dim" in action_lower:
                return f"{mood_tone['suggestion_prefix']} das Licht dimmen"
        
        # Climate actions
        if "climate" in action_lower or "temperatur" in action_lower:
            return f"{mood_tone['suggestion_prefix']} die Temperatur anpassen"
        
        # Media actions
        if "media" in action_lower or "music" in action_lower:
            return f"{mood_tone['suggestion_prefix']} Musik starten"
        
        # Generic fallback
        return f"{mood_tone['suggestion_prefix']} {action}"
    
    def get_context(self) -> VoiceContext:
        """Get current voice context."""
        return self._context
    
    def get_context_dict(self) -> Dict[str, Any]:
        """Get voice context as dict for API response."""
        return {
            "mood": {
                "dominant": self._context.dominant_mood,
                "confidence": self._context.mood_confidence,
                "contributors": self._context.mood_contributors,
            },
            "zone": {
                "current": self._context.current_zone,
                "presence": self._context.zone_presence,
            },
            "voice": {
                "tone": self.MOOD_TONES.get(
                    self._context.dominant_mood,
                    self.MOOD_TONES["relax"]
                )["tone"],
                "greeting": self.MOOD_TONES.get(
                    self._context.dominant_mood,
                    self.MOOD_TONES["relax"]
                )["greeting"],
                "suggestions": self._context.voice_suggestions,
            },
            "metadata": {
                "last_update": self._context.last_update,
                "context_version": self._context.context_version,
            },
        }
    
    def get_mood_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent mood history for trend analysis."""
        return self._mood_history[-limit:]
    
    def get_voice_prompt(self) -> str:
        """Get a voice prompt based on current context.
        
        Use in HA Assist templates:
        ```
        {{ state_attr('sensor.ai_copilot_voice_context', 'voice_prompt') }}
        ```
        """
        mood_tone = self.MOOD_TONES.get(
            self._context.dominant_mood,
            self.MOOD_TONES["relax"]
        )
        
        # Build context-aware prompt
        parts = [f"Der Nutzer ist gerade {mood_tone['greeting']}."]
        
        if self._context.zone_presence:
            zones = ", ".join(self._context.zone_presence[:3])
            parts.append(f"Anwesend in: {zones}.")
        
        if self._context.voice_suggestions:
            parts.append(f"Vorschläge: {'; '.join(self._context.voice_suggestions[:2])}.")
        
        return " ".join(parts)


# Singleton instance
_voice_context_provider: Optional[VoiceContextProvider] = None


def get_voice_context_provider() -> VoiceContextProvider:
    """Get the singleton voice context provider."""
    global _voice_context_provider
    if _voice_context_provider is None:
        _voice_context_provider = VoiceContextProvider()
    return _voice_context_provider