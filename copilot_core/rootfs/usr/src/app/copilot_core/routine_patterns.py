"""
Routine Pattern Extraction - Lernt aus User-Verhalten für tageszeit-/wochentagsbasierte Routinen

V7.11.0 - PilotSuite Core
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Pattern storage path
ROUTINE_PATTERNS_PATH = "/data/routine_patterns.json"

# Time buckets for routine analysis
TIME_BUCKETS = {
    "night": (0, 5),
    "early_morning": (5, 8),
    "morning": (8, 10),
    "forenoon": (10, 12),
    "noon": (12, 14),
    "afternoon": (14, 17),
    "evening": (17, 21),
    "late_evening": (21, 24),
}


def _get_time_bucket(hour: int) -> str:
    """Bestimme Time Bucket aus Stunde."""
    for bucket, (start, end) in TIME_BUCKETS.items():
        if start <= hour < end:
            return bucket
    return "night"


class RoutinePatternExtractor:
    """
    Extraktion von tageszeit-/wochentagsbasierten Routinen.
    
    Lernt:
    - Typische Aktionsmuster zu bestimmten Tageszeiten
    - Wochentag-spezifische Unterschiede
    - Regelmäßige Wiederholungen (daily, weekly)
    """
    
    def __init__(self):
        self._patterns: dict = {
            "actions_by_time": defaultdict(list),      # bucket -> [actions]
            "actions_by_weekday": defaultdict(list),   # weekday -> [actions]
            "action_sequences": [],                   # consecutive action pairs
            "recent_actions": [],                    # last N actions
        }
        self._load_patterns()
    
    def _load_patterns(self):
        """Lade gespeicherte Patterns."""
        try:
            with open(ROUTINE_PATTERNS_PATH, "r") as f:
                data = json.load(f)
                self._patterns["actions_by_time"] = defaultdict(list, data.get("actions_by_time", {}))
                self._patterns["actions_by_weekday"] = defaultdict(list, data.get("actions_by_weekday", {}))
                self._patterns["action_sequences"] = data.get("action_sequences", [])
                self._patterns["recent_actions"] = data.get("recent_actions", [])
        except FileNotFoundError:
            logger.info("No routine patterns found, starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load routine patterns: {e}")
    
    def _save_patterns(self):
        """Speichere Patterns."""
        try:
            import os
            os.makedirs(os.path.dirname(ROUTINE_PATTERNS_PATH), exist_ok=True)
            patterns_to_save = {
                "actions_by_time": dict(self._patterns["actions_by_time"]),
                "actions_by_weekday": dict(self._patterns["actions_by_weekday"]),
                "action_sequences": self._patterns["action_sequences"][-100:],
                "recent_actions": self._patterns["recent_actions"][-100:],
            }
            with open(ROUTINE_PATTERNS_PATH, "w") as f:
                json.dump(patterns_to_save, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save routine patterns: {e}")
    
    def record_action(self, action_type: str, entity_id: str, state: Any, context: Optional[dict] = None):
        """
        Record a user action to learn routines.
        
        Args:
            action_type: Type of action (e.g., "light_turned_on", "scene_activated")
            entity_id: Entity that was affected
            state: New state or value
            context: Optional additional context
        """
        now = datetime.now(timezone.utc)
        time_bucket = _get_time_bucket(now.hour)
        weekday = now.strftime("%A").lower()
        
        action = {
            "type": action_type,
            "entity_id": entity_id,
            "state": str(state) if state is not None else None,
            "timestamp": now.isoformat(),
            "time_bucket": time_bucket,
            "weekday": weekday,
            "context": context or {},
        }
        
        # Record in time bucket
        self._patterns["actions_by_time"][time_bucket].append(action)
        
        # Record in weekday bucket
        self._patterns["actions_by_weekday"][weekday].append(action)
        
        # Record sequence (with previous action)
        if self._patterns["recent_actions"]:
            prev = self._patterns["recent_actions"][-1]
            sequence = {
                "first": {"type": prev["type"], "entity_id": prev["entity_id"]},
                "second": {"type": action_type, "entity_id": entity_id},
                "timestamp": now.isoformat(),
            }
            self._patterns["action_sequences"].append(sequence)
        
        # Keep recent actions
        self._patterns["recent_actions"].append(action)
        if len(self._patterns["recent_actions"]) > 200:
            self._patterns["recent_actions"] = self._patterns["recent_actions"][-200:]
        
        self._save_patterns()
        logger.debug(f"Recorded action: {action_type} on {entity_id}")
    
    def predict_next_action(self, current_time: Optional[datetime] = None) -> list[dict]:
        """
        Predict next likely actions based on current time and learned patterns.
        
        Args:
            current_time: Optional time override (defaults to now)
        
        Returns:
            List of predicted next actions with confidence
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        time_bucket = _get_time_bucket(current_time.hour)
        weekday = current_time.strftime("%A").lower()
        
        predictions = defaultdict(lambda: {"count": 0, "confidence": 0.0})
        
        # Get actions for this time bucket
        time_actions = self._patterns["actions_by_time"].get(time_bucket, [])
        
        # Get actions for this weekday
        weekday_actions = self._patterns["actions_by_weekday"].get(weekday, [])
        
        # Combine and count
        all_actions = time_actions[-30:] + weekday_actions[-30:]
        
        for action in all_actions:
            key = f"{action['type']}:{action['entity_id']}"
            predictions[key]["count"] += 1
        
        # Calculate confidence
        total = len(time_actions) + len(weekday_actions)
        if total == 0:
            return []
        
        results = []
        for key, data in predictions.items():
            action_type, entity_id = key.split(":", 1)
            confidence = min(1.0, data["count"] / 3.0)
            results.append({
                "action_type": action_type,
                "entity_id": entity_id,
                "confidence": round(confidence, 2),
                "count": data["count"],
                "time_bucket": time_bucket,
                "weekday": weekday,
            })
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:5]
    
    def get_typical_routine(self, weekday_type: str = "weekday") -> list[dict]:
        """
        Get typical daily routine.
        
        Args:
            weekday_type: "weekday" or "weekend"
        
        Returns:
            Ordered list of typical actions by time bucket
        """
        if weekday_type == "weekend":
            weekdays = ["saturday", "sunday"]
        else:
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        
        routine = {}
        
        for weekday in weekdays:
            actions = self._patterns["actions_by_weekday"].get(weekday, [])
            for action in actions:
                bucket = action["time_bucket"]
                if bucket not in routine:
                    routine[bucket] = defaultdict(int)
                key = f"{action['type']}:{action['entity_id']}"
                routine[bucket][key] += 1
        
        # Convert to ordered list
        ordered_buckets = ["early_morning", "morning", "forenoon", "noon", "afternoon", "evening", "late_evening", "night"]
        
        result = []
        for bucket in ordered_buckets:
            if bucket in routine:
                actions = routine[bucket]
                top_actions = sorted(actions.items(), key=lambda x: x[1], reverse=True)[:3]
                result.append({
                    "time_bucket": bucket,
                    "typical_actions": [
                        {"action": k.split(":", 1)[0], "entity": k.split(":", 1)[1], "count": v}
                        for k, v in top_actions
                    ],
                })
        
        return result
    
    def get_pattern_summary(self) -> dict:
        """Get summary of learned patterns."""
        return {
            "total_actions": len(self._patterns["recent_actions"]),
            "unique_action_types": len(set(a["type"] for a in self._patterns["recent_actions"])),
            "time_buckets_with_data": [k for k, v in self._patterns["actions_by_time"].items() if v],
            "weekdays_with_data": [k for k, v in self._patterns["actions_by_weekday"].items() if v],
            "sequences_learned": len(self._patterns["action_sequences"]),
        }
    
    def clear_patterns(self):
        """Clear all learned patterns."""
        self._patterns = {
            "actions_by_time": defaultdict(list),
            "actions_by_weekday": defaultdict(list),
            "action_sequences": [],
            "recent_actions": [],
        }
        self._save_patterns()
        logger.info("Cleared all routine patterns")


# Global instance
_routine_pattern_extractor: Optional[RoutinePatternExtractor] = None


def get_routine_pattern_extractor() -> RoutinePatternExtractor:
    """Get or create the global RoutinePatternExtractor instance."""
    global _routine_pattern_extractor
    if _routine_pattern_extractor is None:
        _routine_pattern_extractor = RoutinePatternExtractor()
    return _routine_pattern_extractor


__all__ = [
    "RoutinePatternExtractor",
    "get_routine_pattern_extractor",
]
