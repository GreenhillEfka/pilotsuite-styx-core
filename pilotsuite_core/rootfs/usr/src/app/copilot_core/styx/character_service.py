# Migrated from pilotsuite-styx-ha (core/character/service.py)
"""Character Service - Manage Styx personality presets.

Controls how Styx behaves:
- Mood weight application (character shapes mood perception)
- Suggestion gating (frequency, confidence threshold, quiet hours)
- Auto-execution thresholds
- Voice formatting (greetings, confirmations, alerts)

No HA dependencies — pure personality logic.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List

from .character_models import (
    AlertConfig,
    CharacterConfig,
    CharacterMode,
    CharacterPreset,
)


class CharacterService:
    """Service to manage character presets and apply them to mood/suggestions."""

    def __init__(self) -> None:
        self._config = CharacterConfig()
        self._presets: Dict[CharacterMode, CharacterPreset] = {
            CharacterMode.ASSISTANT: CharacterPreset.assistant(),
            CharacterMode.COMPANION: CharacterPreset.companion(),
            CharacterMode.GUARDIAN: CharacterPreset.guardian(),
            CharacterMode.EFFICIENCY: CharacterPreset.efficiency(),
            CharacterMode.RELAXED: CharacterPreset.relaxed(),
        }

    def get_current_preset(self) -> CharacterPreset:
        """Get the current active preset."""
        if self._config.custom_preset:
            return self._config.custom_preset
        return self._presets.get(self._config.current_mode, CharacterPreset.companion())

    def set_mode(self, mode: CharacterMode) -> None:
        """Set the character mode."""
        self._config.current_mode = mode
        self._config.custom_preset = None

    def set_custom_preset(self, preset: CharacterPreset) -> None:
        """Set a custom preset."""
        self._config.custom_preset = preset

    def get_available_modes(self) -> List[Dict[str, Any]]:
        """Get list of available modes with info."""
        return [
            {
                "mode": mode.value,
                "display_name": preset.display_name,
                "description": preset.description,
                "icon": preset.icon,
            }
            for mode, preset in self._presets.items()
        ]

    # ── Mood Integration ─────────────────────────────────────────────

    def apply_mood_weights(self, base_mood: Dict[str, float]) -> Dict[str, float]:
        """Apply character mood weights to base mood scores."""
        preset = self.get_current_preset()
        weights = preset.mood_weights
        return {
            mood_type: score * getattr(weights, mood_type.lower(), 1.0)
            for mood_type, score in base_mood.items()
        }

    # ── Suggestion Gating ────────────────────────────────────────────

    def should_suggest(self, hour: int, confidence: float, suggestion_count: int) -> bool:
        """Determine if a suggestion should be shown based on character settings."""
        preset = self.get_current_preset()
        suggestions = preset.suggestions

        if hour in suggestions.quiet_hours:
            return False
        if suggestion_count >= suggestions.max_per_hour:
            return False
        if suggestions.frequency == "silent":
            return False
        if suggestions.frequency == "reactive":
            return confidence >= 0.95
        if suggestions.frequency == "proactive":
            return confidence >= 0.5
        # balanced
        return confidence >= 0.7

    def should_auto_execute(self, confidence: float) -> bool:
        """Determine if a suggestion should be auto-executed."""
        preset = self.get_current_preset()
        threshold = preset.suggestions.auto_execute_threshold
        aggressiveness = preset.suggestions.aggressiveness
        effective_threshold = threshold - (aggressiveness * 0.1)
        return confidence >= effective_threshold

    # ── Voice Formatting ─────────────────────────────────────────────

    def format_suggestion(self, suggestion_text: str) -> str:
        """Format a suggestion with character voice prefix."""
        preset = self.get_current_preset()
        return f"{preset.voice.suggestions_prefix} {suggestion_text}"

    def format_alert(self, alert_text: str, alert_type: str = "general") -> str:
        """Format an alert with character voice. Returns '' if alert type is disabled."""
        preset = self.get_current_preset()
        alert_type_map = {
            "security": preset.alerts.security,
            "energy": preset.alerts.energy,
            "comfort": preset.alerts.comfort,
            "maintenance": preset.alerts.maintenance,
            "safety_critical": preset.alerts.safety_critical,
        }
        if not alert_type_map.get(alert_type, True):
            return ""
        return f"{preset.voice.alerts_prefix} {alert_text}"

    def get_greeting(self) -> str:
        """Get character greeting."""
        return self.get_current_preset().voice.greeting

    def get_confirmation(self) -> str:
        """Get random confirmation message."""
        return random.choice(self.get_current_preset().voice.confirmations)  # noqa: S311

    def get_goodbye(self) -> str:
        """Get random goodbye message."""
        return random.choice(self.get_current_preset().voice.goodbyes)  # noqa: S311

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Export current configuration as dict."""
        preset = self.get_current_preset()
        return {
            "current_mode": self._config.current_mode.value,
            "preset": {
                "name": preset.name.value,
                "display_name": preset.display_name,
                "description": preset.description,
                "icon": preset.icon,
                "mood_weights": {
                    "relax": preset.mood_weights.relax,
                    "focus": preset.mood_weights.focus,
                    "active": preset.mood_weights.active,
                    "sleep": preset.mood_weights.sleep,
                    "away": preset.mood_weights.away,
                    "alert": preset.mood_weights.alert,
                    "social": preset.mood_weights.social,
                    "recovery": preset.mood_weights.recovery,
                },
                "suggestions": {
                    "frequency": preset.suggestions.frequency,
                    "aggressiveness": preset.suggestions.aggressiveness,
                    "max_per_hour": preset.suggestions.max_per_hour,
                },
                "voice": {
                    "tone": preset.voice.tone,
                    "greeting": preset.voice.greeting,
                },
            },
        }
