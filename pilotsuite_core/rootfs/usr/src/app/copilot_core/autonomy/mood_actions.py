"""Mood-Action-Mapping — Statische Tabellen + User-Overrides.

Maps mood states to concrete light/music actions for autonomous execution.
Weather overlay adjusts music choices based on WeatherNeuron scores.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

_OVERRIDES_PATH = os.environ.get(
    "MOOD_ACTIONS_PATH", "/data/mood_actions.json"
)


@dataclass
class MoodActionSet:
    """Concrete actions derived from a mood state."""

    mood: str
    light_scene: str = ""
    brightness_pct: int = 0
    color_temp_k: int = 0
    music_favorite: str = ""
    music_volume_pct: int = 0
    music_action: str = "none"  # play | pause | none

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MoodActionSet:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Default Mood-Action Table ───────────────────────────────────────────────

_DEFAULT_ACTIONS: Dict[str, MoodActionSet] = {
    "relax": MoodActionSet(
        mood="relax",
        light_scene="relax",
        brightness_pct=50,
        color_temp_k=2700,
        music_favorite="Chill Lounge",
        music_volume_pct=25,
        music_action="play",
    ),
    "focus": MoodActionSet(
        mood="focus",
        light_scene="focus",
        brightness_pct=90,
        color_temp_k=4500,
        music_favorite="",
        music_volume_pct=0,
        music_action="pause",
    ),
    "sleep": MoodActionSet(
        mood="sleep",
        light_scene="night_light",
        brightness_pct=5,
        color_temp_k=2200,
        music_favorite="Sleep Sounds",
        music_volume_pct=15,
        music_action="play",
    ),
    "active": MoodActionSet(
        mood="active",
        light_scene="energize",
        brightness_pct=100,
        color_temp_k=5000,
        music_favorite="Feel Good Hits",
        music_volume_pct=40,
        music_action="play",
    ),
    "social": MoodActionSet(
        mood="social",
        light_scene="cozy",
        brightness_pct=60,
        color_temp_k=3000,
        music_favorite="Party Mix",
        music_volume_pct=45,
        music_action="play",
    ),
    "away": MoodActionSet(
        mood="away",
        light_scene="off",
        brightness_pct=0,
        color_temp_k=0,
        music_favorite="",
        music_volume_pct=0,
        music_action="pause",
    ),
    "alert": MoodActionSet(
        mood="alert",
        light_scene="energize",
        brightness_pct=100,
        color_temp_k=5000,
        music_favorite="",
        music_volume_pct=0,
        music_action="none",
    ),
    "recovery": MoodActionSet(
        mood="recovery",
        light_scene="dim",
        brightness_pct=30,
        color_temp_k=3000,
        music_favorite="Calm Nature",
        music_volume_pct=20,
        music_action="play",
    ),
}

# Weather uplift: cloudy/rainy + non-active mood → switch music to feel-good
_WEATHER_UPLIFT_FAVORITE = "Sunny Feel-Good"
_WEATHER_UPLIFT_THRESHOLD = 0.4  # weather_score < this triggers uplift


class MoodActionMapper:
    """Lookup mood actions with optional user overrides and weather overlay."""

    def __init__(self, overrides_path: str | None = None) -> None:
        self._overrides_path = overrides_path or _OVERRIDES_PATH
        self._overrides: Dict[str, MoodActionSet] = {}
        self._load_overrides()

    # ── Persistence ─────────────────────────────────────────────────────

    def _load_overrides(self) -> None:
        """Load user overrides from JSON file."""
        if not os.path.exists(self._overrides_path):
            return
        try:
            with open(self._overrides_path, "r") as f:
                data = json.load(f)
            for mood, action_data in data.items():
                action_data["mood"] = mood
                self._overrides[mood] = MoodActionSet.from_dict(action_data)
            _LOGGER.info("Loaded %d mood-action overrides", len(self._overrides))
        except Exception:
            _LOGGER.exception("Failed to load mood-action overrides from %s", self._overrides_path)

    def _save_overrides(self) -> None:
        """Persist user overrides to JSON file."""
        try:
            data = {mood: action.to_dict() for mood, action in self._overrides.items()}
            os.makedirs(os.path.dirname(self._overrides_path) or "/data", exist_ok=True)
            with open(self._overrides_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            _LOGGER.exception("Failed to save mood-action overrides")

    # ── Public API ──────────────────────────────────────────────────────

    def get_mood_actions(
        self,
        mood: str,
        weather_score: float | None = None,
    ) -> MoodActionSet:
        """Get actions for a mood, applying weather overlay if applicable.

        Args:
            mood: Current mood state (e.g. "relax", "focus").
            weather_score: 0.0 (bad weather) to 1.0 (great weather).
                           If < threshold and mood is not high-energy, uplift music.

        Returns:
            MoodActionSet with concrete actions.
        """
        # User override takes priority
        base = self._overrides.get(mood) or _DEFAULT_ACTIONS.get(mood)
        if base is None:
            _LOGGER.debug("No actions mapped for mood %r, returning neutral", mood)
            return MoodActionSet(mood=mood)

        # Copy to avoid mutating stored data
        result = MoodActionSet.from_dict(base.to_dict())

        # Weather overlay: uplift music on cloudy/rainy days for calm moods
        if (
            weather_score is not None
            and weather_score < _WEATHER_UPLIFT_THRESHOLD
            and mood not in ("active", "alert", "away", "focus")
            and result.music_action == "play"
        ):
            result.music_favorite = _WEATHER_UPLIFT_FAVORITE
            _LOGGER.debug(
                "Weather overlay: score=%.2f < %.2f → music switched to %r",
                weather_score, _WEATHER_UPLIFT_THRESHOLD, _WEATHER_UPLIFT_FAVORITE,
            )

        return result

    def set_override(self, mood: str, overrides: Dict[str, Any]) -> MoodActionSet:
        """Set user overrides for a mood.

        Args:
            mood: Mood to override.
            overrides: Fields to override (partial update).

        Returns:
            Updated MoodActionSet.
        """
        base = self._overrides.get(mood) or _DEFAULT_ACTIONS.get(mood)
        if base is None:
            base = MoodActionSet(mood=mood)

        merged = base.to_dict()
        merged.update(overrides)
        merged["mood"] = mood

        action_set = MoodActionSet.from_dict(merged)
        self._overrides[mood] = action_set
        self._save_overrides()
        _LOGGER.info("Override saved for mood %r", mood)
        return action_set

    def get_all_actions(self) -> Dict[str, Dict[str, Any]]:
        """Return full mood-action table (defaults + overrides merged)."""
        result = {}
        for mood, action in _DEFAULT_ACTIONS.items():
            effective = self._overrides.get(mood, action)
            result[mood] = effective.to_dict()
            result[mood]["overridden"] = mood in self._overrides
        return result

    def remove_override(self, mood: str) -> bool:
        """Remove user override for a mood (revert to default)."""
        if mood in self._overrides:
            del self._overrides[mood]
            self._save_overrides()
            return True
        return False
