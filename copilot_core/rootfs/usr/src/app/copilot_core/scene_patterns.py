"""
Scene Pattern Extraction - Lernt aus User-Verhalten wann Scenes aktiviert werden

V7.11.0 - PilotSuite Core
"""

import json
import logging
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# Pattern storage path
PATTERNS_PATH = "/data/scene_patterns.json"


class ScenePatternExtractor:
    """
    Extraktion von Scene-Aktivierungsmustern aus User-Verhalten.
    
    Lernt:
    - Tageszeit-basierte Muster (morgens, abends, nachts)
    - Wochentag-basierte Muster (Werktag vs. Wochenende)
    - Kontext-basierte Muster (vor/nach bestimmten Events)
    """
    
    def __init__(self):
        self._patterns: dict = {
            "by_time_of_day": defaultdict(list),  # morning, afternoon, evening, night
            "by_weekday": defaultdict(list),      # monday-sunday
            "by_context": defaultdict(list),       # before_event, after_event
            "recent_activations": [],             # last N activations
        }
        self._load_patterns()
    
    def _load_patterns(self):
        """Lade gespeicherte Patterns."""
        try:
            with open(PATTERNS_PATH, "r") as f:
                self._patterns = json.load(f)
                # Convert lists back to defaultdict for safety
                from collections import defaultdict
                self._patterns["by_time_of_day"] = defaultdict(list, self._patterns.get("by_time_of_day", {}))
                self._patterns["by_weekday"] = defaultdict(list, self._patterns.get("by_weekday", {}))
                self._patterns["by_context"] = defaultdict(list, self._patterns.get("by_context", {}))
        except FileNotFoundError:
            logger.info("No scene patterns found, starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load scene patterns: {e}")
    
    def _save_patterns(self):
        """Speichere Patterns."""
        try:
            import os
            os.makedirs(os.path.dirname(PATTERNS_PATH), exist_ok=True)
            # Convert defaultdict to regular dict for JSON serialization
            patterns_to_save = {
                "by_time_of_day": dict(self._patterns["by_time_of_day"]),
                "by_weekday": dict(self._patterns["by_weekday"]),
                "by_context": dict(self._patterns["by_context"]),
                "recent_activations": self._patterns["recent_activations"][-50:],  # Keep last 50
            }
            with open(PATTERNS_PATH, "w") as f:
                json.dump(patterns_to_save, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save scene patterns: {e}")
    
    def _get_time_bucket(self, dt: datetime) -> str:
        """Bestimme Tageszeit-Bucket."""
        hour = dt.hour
        if 5 <= hour < 9:
            return "morning"
        elif 9 <= hour < 12:
            return "forenoon"
        elif 12 <= hour < 14:
            return "noon"
        elif 14 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"
    
    def _get_weekday_bucket(self, dt: datetime) -> str:
        """Bestimme Wochentag-Bucket."""
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        return weekdays[dt.weekday()]
    
    def record_scene_activation(self, scene_id: str, context: Optional[dict] = None):
        """
        Record a scene activation to learn patterns.
        
        Args:
            scene_id: ID of the activated scene
            context: Optional context (e.g., {"before_event": "arrival", "after_event": "dinner"})
        """
        now = datetime.now(timezone.utc)
        time_bucket = self._get_time_bucket(now)
        weekday_bucket = self._get_weekday_bucket(now)
        
        activation = {
            "scene_id": scene_id,
            "timestamp": now.isoformat(),
            "time_bucket": time_bucket,
            "weekday": weekday_bucket,
            "context": context or {},
        }
        
        # Record in time-based patterns
        self._patterns["by_time_of_day"][time_bucket].append(activation)
        
        # Record in weekday-based patterns
        self._patterns["by_weekday"][weekday_bucket].append(activation)
        
        # Record in context patterns
        if context:
            for ctx_key, ctx_value in context.items():
                self._patterns["by_context"][f"{ctx_key}:{ctx_value}"].append(activation)
        
        # Keep recent activations
        self._patterns["recent_activations"].append(activation)
        if len(self._patterns["recent_activations"]) > 100:
            self._patterns["recent_activations"] = self._patterns["recent_activations"][-100:]
        
        self._save_patterns()
        logger.info(f"Recorded scene activation: {scene_id} at {time_bucket}/{weekday_bucket}")
    
    def suggest_scenes(self, context: Optional[dict] = None) -> list[dict]:
        """
        Propose scene suggestions based on learned patterns.
        
        Args:
            context: Current context (e.g., {"time_bucket": "evening", "weekday": "friday"})
        
        Returns:
            List of suggested scenes with confidence scores
        """
        now = datetime.now(timezone.utc)
        time_bucket = self._get_time_bucket(now)
        weekday_bucket = self._get_weekday_bucket(now)
        
        suggestions = defaultdict(lambda: {"count": 0, "confidence": 0.0, "last_seen": None})
        
        # Check time-of-day patterns
        time_pattern = self._patterns["by_time_of_day"].get(time_bucket, [])
        for act in time_pattern[-20:]:  # Last 20 activations for this time
            scene_id = act["scene_id"]
            suggestions[scene_id]["count"] += 1
            suggestions[scene_id]["last_seen"] = act["timestamp"]
        
        # Check weekday patterns
        weekday_pattern = self._patterns["by_weekday"].get(weekday_bucket, [])
        for act in weekday_pattern[-20:]:
            scene_id = act["scene_id"]
            suggestions[scene_id]["count"] += 1
            suggestions[scene_id]["last_seen"] = act["timestamp"]
        
        # Boost by context if provided
        if context:
            for ctx_key, ctx_value in context.items():
                ctx_key_full = f"{ctx_key}:{ctx_value}"
                ctx_pattern = self._patterns["by_context"].get(ctx_key_full, [])
                for act in ctx_pattern:
                    scene_id = act["scene_id"]
                    suggestions[scene_id]["count"] += 2  # Context is strong signal
                    suggestions[scene_id]["last_seen"] = act["timestamp"]
        
        # Calculate confidence scores
        results = []
        total_activations = len(self._patterns["recent_activations"])
        if total_activations == 0:
            return []
        
        for scene_id, data in suggestions.items():
            confidence = min(1.0, data["count"] / 5.0)  # Max confidence at 5+ activations
            results.append({
                "scene_id": scene_id,
                "confidence": round(confidence, 2),
                "activation_count": data["count"],
                "last_seen": data["last_seen"],
            })
        
        # Sort by confidence
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        return results[:5]  # Top 5 suggestions
    
    def get_pattern_summary(self) -> dict:
        """Get summary of learned patterns."""
        return {
            "total_activations": len(self._patterns["recent_activations"]),
            "unique_scenes": len(set(a["scene_id"] for a in self._patterns["recent_activations"])),
            "by_time_of_day": {k: len(v) for k, v in self._patterns["by_time_of_day"].items()},
            "by_weekday": {k: len(v) for k, v in self._patterns["by_weekday"].items()},
            "by_context": {k: len(v) for k, v in self._patterns["by_context"].items()},
        }
    
    def clear_patterns(self):
        """Clear all learned patterns."""
        self._patterns = {
            "by_time_of_day": defaultdict(list),
            "by_weekday": defaultdict(list),
            "by_context": defaultdict(list),
            "recent_activations": [],
        }
        self._save_patterns()
        logger.info("Cleared all scene patterns")


# Global instance
_scene_pattern_extractor: Optional[ScenePatternExtractor] = None


def get_scene_pattern_extractor() -> ScenePatternExtractor:
    """Get or create the global ScenePatternExtractor instance."""
    global _scene_pattern_extractor
    if _scene_pattern_extractor is None:
        _scene_pattern_extractor = ScenePatternExtractor()
    return _scene_pattern_extractor


__all__ = [
    "ScenePatternExtractor",
    "get_scene_pattern_extractor",
]
