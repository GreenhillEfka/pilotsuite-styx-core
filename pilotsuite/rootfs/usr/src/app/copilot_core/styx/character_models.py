# Migrated from pilotsuite-styx-ha (core/character/models.py)
"""Character Models - Personality presets for Styx.

5 Character modes that shape how Styx behaves:
- Mood weight multipliers
- Suggestion frequency + aggressiveness
- Voice tone + messages
- Alert filtering
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class CharacterMode(Enum):
    """Available character modes."""
    ASSISTANT = "assistant"      # Neutral, efficient, formal
    COMPANION = "companion"      # Warm, proactive, friendly
    GUARDIAN = "guardian"         # Security-focused, cautious
    EFFICIENCY = "efficiency"    # Optimization-focused, direct
    RELAXED = "relaxed"          # Calm, minimal suggestions


@dataclass
class MoodWeights:
    """Mood weight multipliers for character."""
    relax: float = 1.0
    focus: float = 1.0
    active: float = 1.0
    sleep: float = 1.0
    away: float = 1.0
    alert: float = 1.0
    social: float = 1.0
    recovery: float = 1.0


@dataclass
class SuggestionConfig:
    """Suggestion behavior for character."""
    frequency: str = "balanced"      # proactive, balanced, reactive, silent
    aggressiveness: float = 0.5      # 0.0 = wait for user, 1.0 = auto-execute
    auto_execute_threshold: float = 0.95
    max_per_hour: int = 5
    quiet_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])


@dataclass
class VoiceConfig:
    """Voice behavior for character."""
    tone: str = "neutral"            # formal, friendly, casual, cautious
    greeting: str = "Bereit."
    goodbyes: List[str] = field(default_factory=lambda: ["Bis gleich."])
    confirmations: List[str] = field(default_factory=lambda: ["Erledigt.", "Verstanden."])
    errors: List[str] = field(default_factory=lambda: ["Das hat nicht geklappt."])
    suggestions_prefix: str = "Ich empfehle:"
    alerts_prefix: str = "Achtung:"


@dataclass
class AlertConfig:
    """Alert behavior for character."""
    security: bool = True
    energy: bool = True
    comfort: bool = True
    maintenance: bool = True
    safety_critical: bool = True  # Always on for guardian


@dataclass
class CharacterPreset:
    """A complete character preset."""
    name: CharacterMode
    display_name: str
    description: str
    mood_weights: MoodWeights
    suggestions: SuggestionConfig
    voice: VoiceConfig
    alerts: AlertConfig
    privacy_level: str = "balanced"  # strict, balanced, learning
    icon: str = "\U0001f916"

    @classmethod
    def assistant(cls) -> CharacterPreset:
        return cls(
            name=CharacterMode.ASSISTANT,
            display_name="Assistent",
            description="Neutral, effizient und sachlich. Hilft bei Bedarf.",
            mood_weights=MoodWeights(),
            suggestions=SuggestionConfig(
                frequency="reactive", aggressiveness=0.3, max_per_hour=3,
            ),
            voice=VoiceConfig(
                tone="formal",
                greeting="Guten Tag. Wie kann ich helfen?",
                suggestions_prefix="Vorschlag:",
            ),
            alerts=AlertConfig(),
            icon="\U0001f916",
        )

    @classmethod
    def companion(cls) -> CharacterPreset:
        return cls(
            name=CharacterMode.COMPANION,
            display_name="Begleiter",
            description="Warm, proaktiv und freundlich. Kennt deine Vorlieben.",
            mood_weights=MoodWeights(relax=1.2, social=1.1, recovery=1.1),
            suggestions=SuggestionConfig(
                frequency="proactive", aggressiveness=0.6,
                max_per_hour=8, quiet_hours=[1, 2, 3, 4, 5],
            ),
            voice=VoiceConfig(
                tone="friendly",
                greeting="Hey! Wie kann ich helfen?",
                goodbyes=["Bis gleich!", "Gern geschehen!", "Sch\u00f6nen Tag!"],
                confirmations=["Alles klar!", "Mach ich!", "Erledigt!"],
                suggestions_prefix="Ich habe da eine Idee:",
            ),
            alerts=AlertConfig(comfort=True, energy=True, security=True),
            icon="\U0001f99e",
        )

    @classmethod
    def guardian(cls) -> CharacterPreset:
        return cls(
            name=CharacterMode.GUARDIAN,
            display_name="W\u00e4chter",
            description="Sicherheitsfokussiert und vorsichtig. H\u00e4lt dein Zuhause sicher.",
            mood_weights=MoodWeights(alert=1.5, away=1.3),
            suggestions=SuggestionConfig(
                frequency="balanced", aggressiveness=0.4,
                auto_execute_threshold=0.99, max_per_hour=3,
            ),
            voice=VoiceConfig(
                tone="cautious",
                greeting="System aktiv. Alle Sensoren online.",
                suggestions_prefix="Sicherheitshinweis:",
                alerts_prefix="Warnung:",
            ),
            alerts=AlertConfig(
                security=True, safety_critical=True, maintenance=True,
                energy=False, comfort=False,
            ),
            icon="\U0001f6e1\ufe0f",
        )

    @classmethod
    def efficiency(cls) -> CharacterPreset:
        return cls(
            name=CharacterMode.EFFICIENCY,
            display_name="Optimierer",
            description="Energiebewusst und direkt. Spart Ressourcen.",
            mood_weights=MoodWeights(away=1.3, sleep=1.2),
            suggestions=SuggestionConfig(
                frequency="proactive", aggressiveness=0.7,
                auto_execute_threshold=0.9, max_per_hour=10,
            ),
            voice=VoiceConfig(
                tone="direct",
                greeting="Bereit f\u00fcr Optimierung.",
                suggestions_prefix="Einsparpotenzial:",
            ),
            alerts=AlertConfig(energy=True, maintenance=True),
            icon="\u26a1",
        )

    @classmethod
    def relaxed(cls) -> CharacterPreset:
        return cls(
            name=CharacterMode.RELAXED,
            display_name="Entspannt",
            description="Ruhig und minimalistisch. Nur das N\u00f6tigste.",
            mood_weights=MoodWeights(relax=1.5, recovery=1.3),
            suggestions=SuggestionConfig(
                frequency="silent", aggressiveness=0.1,
                auto_execute_threshold=0.99, max_per_hour=2,
            ),
            voice=VoiceConfig(
                tone="casual",
                greeting="Alles gut.",
                goodbyes=["Bis dann."],
                confirmations=["Ok."],
                suggestions_prefix="Falls du magst:",
            ),
            alerts=AlertConfig(safety_critical=True),
            icon="\U0001f60c",
        )


@dataclass
class CharacterConfig:
    """Runtime character configuration."""
    current_mode: CharacterMode = CharacterMode.COMPANION
    custom_preset: Optional[CharacterPreset] = None
