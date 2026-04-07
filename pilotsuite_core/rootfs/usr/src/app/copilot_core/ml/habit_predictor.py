# Migrated from pilotsuite-styx-ha
"""
Habit Prediction Module - Predicts user routines and patterns.

Standalone prediction engine without HA dependencies. Uses time-based
pattern detection, device sequence modeling, mood-aware confidence
scoring, and per-user tracking.

Storage: /data/ml/ (default persistence path)
"""

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_PATH = "/data/ml/"


class HabitPredictor:
    """
    Predicts user habits and routines based on historical patterns.

    Features:
    - Time-based pattern detection (hour-of-day + day-of-week)
    - Device usage prediction
    - Activity sequence modeling (A->B device chains)
    - Confidence scoring with recency weighting
    - Mood-pattern tracking (mood + event_type correlation)
    """

    def __init__(
        self,
        min_samples_per_pattern: int = 3,
        prediction_horizon_hours: int = 12,
        confidence_threshold: float = 0.5,
        enabled: bool = True,
        storage_path: str = DEFAULT_STORAGE_PATH,
    ):
        """
        Initialize the habit predictor.

        Args:
            min_samples_per_pattern: Minimum occurrences to recognize a pattern.
            prediction_horizon_hours: How far ahead to predict (hours).
            confidence_threshold: Minimum confidence for predictions.
            enabled: Whether the predictor is active.
            storage_path: Directory for persistence (default /data/ml/).
        """
        self.min_samples_per_pattern = min_samples_per_pattern
        self.prediction_horizon_hours = prediction_horizon_hours
        self.confidence_threshold = confidence_threshold
        self.enabled = enabled
        self.storage_path = storage_path

        # Pattern storage
        self.device_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self.sequence_patterns: Dict[str, List[List[str]]] = defaultdict(list)
        self.time_patterns: Dict[str, Dict[int, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Mood-aware patterns
        self.mood_patterns: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Statistics
        self.pattern_confidence: Dict[str, float] = {}
        self.last_prediction_time: Dict[str, float] = {}

        self._is_initialized = False

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def observe(
        self,
        device_id: str,
        event_type: str,
        timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Observe a device event and update patterns.

        Args:
            device_id: ID of the device.
            event_type: Type of event (on, off, state_change, etc.).
            timestamp: Epoch seconds when the event occurred.
            context: Additional context (mood, device_chain, user, ...).
        """
        if not self.enabled:
            return

        if timestamp is None:
            timestamp = time.time()

        if context is None:
            context = {}

        # Update device patterns
        self._update_device_pattern(device_id, event_type, timestamp)

        # Update time patterns
        self._update_time_pattern(device_id, event_type, timestamp)

        # Update mood patterns if mood context available
        if context.get("mood") and context["mood"] != "unknown":
            self._update_mood_pattern(
                device_id, event_type, context["mood"], timestamp
            )

        # Update sequence patterns if we have a device chain
        if context.get("device_chain"):
            self._update_sequence_pattern(
                device_id,
                context["device_chain"],
                timestamp,
            )

        self._is_initialized = True

    # ------------------------------------------------------------------
    # Internal pattern updates
    # ------------------------------------------------------------------

    def _update_device_pattern(
        self,
        device_id: str,
        event_type: str,
        timestamp: float,
    ) -> None:
        """Update device event pattern."""
        self.device_patterns[device_id].append(
            {
                "event_type": event_type,
                "timestamp": timestamp,
            }
        )

        # Keep only recent events (30 days)
        cutoff = timestamp - (30 * 24 * 3600)
        self.device_patterns[device_id] = [
            p for p in self.device_patterns[device_id] if p["timestamp"] >= cutoff
        ]

    def _update_time_pattern(
        self,
        device_id: str,
        event_type: str,
        timestamp: float,
    ) -> None:
        """Update time-based patterns (hour + day-of-week)."""
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day_of_week = dt.weekday()

        pattern_key = f"{device_id}_{event_type}"
        self.time_patterns[pattern_key][hour].append(timestamp)
        self.time_patterns[pattern_key][f"day_{day_of_week}"].append(timestamp)

    def _update_mood_pattern(
        self,
        device_id: str,
        event_type: str,
        mood: str,
        timestamp: float,
    ) -> None:
        """Update mood-associated patterns."""
        pattern_key = f"{device_id}_{event_type}"
        self.mood_patterns[pattern_key][mood].append(timestamp)

        # Keep only recent events (30 days)
        cutoff = timestamp - (30 * 24 * 3600)
        for mood_key in list(self.mood_patterns[pattern_key]):
            self.mood_patterns[pattern_key][mood_key] = [
                t
                for t in self.mood_patterns[pattern_key][mood_key]
                if t >= cutoff
            ]

    def _update_sequence_pattern(
        self,
        device_id: str,
        device_chain: List[str],
        timestamp: float,
    ) -> None:
        """Update sequence patterns for device chains (A->B->C)."""
        pattern_key = device_chain[0]  # Start device as key

        # Limit sequence length
        sequence = device_chain[:10]
        self.sequence_patterns[pattern_key].append(sequence)

        # Keep only recent sequences (rough heuristic)
        cutoff = timestamp - (30 * 24 * 3600)
        self.sequence_patterns[pattern_key] = [
            seq
            for seq in self.sequence_patterns[pattern_key]
            if self._sequence_timestamp(seq, timestamp) >= cutoff
        ]

    @staticmethod
    def _sequence_timestamp(sequence: List[str], current_time: float) -> float:
        """Get approximate timestamp for a sequence (heuristic)."""
        return current_time - (len(sequence) * 5)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        device_id: str,
        event_type: str,
        timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Predict the likelihood of a device event occurring.

        Args:
            device_id: ID of the device.
            event_type: Type of event to predict.
            timestamp: Epoch seconds for the prediction window.
            context: Optional context including ``mood`` for mood-aware
                     confidence blending.

        Returns:
            Prediction dict with ``predicted``, ``confidence``, ``details``,
            ``device_id``, and ``event_type``.
        """
        if not self.enabled or not self._is_initialized:
            return {
                "predicted": False,
                "confidence": 0.0,
                "details": {},
            }

        if timestamp is None:
            timestamp = time.time()

        if context is None:
            context = {}

        pattern_key = f"{device_id}_{event_type}"

        # Base prediction from time patterns
        prediction = self._predict_pattern(pattern_key, timestamp)

        # Mood-aware adjustment
        current_mood = context.get("mood")
        if current_mood and current_mood != "unknown":
            mood_confidence = self._get_mood_confidence(pattern_key, current_mood)
            if mood_confidence > 0:
                base_conf = prediction.get("confidence", 0)
                blended = (base_conf * 0.6) + (mood_confidence * 0.4)
                prediction["confidence"] = blended
                prediction["predicted"] = blended >= self.confidence_threshold
                prediction["mood_adjusted"] = True
                prediction["mood_confidence"] = mood_confidence

        self.last_prediction_time[pattern_key] = time.time()

        return {
            "predicted": prediction["predicted"],
            "confidence": prediction["confidence"],
            "details": prediction.get("details", {}),
            "device_id": device_id,
            "event_type": event_type,
        }

    def _get_mood_confidence(self, pattern_key: str, mood: str) -> float:
        """Get confidence based on mood-specific historical patterns."""
        mood_times = self.mood_patterns.get(pattern_key, {}).get(mood, [])

        if len(mood_times) < self.min_samples_per_pattern:
            return 0.0

        now = time.time()
        recent_count = sum(1 for t in mood_times if t > now - (7 * 24 * 3600))
        total_count = len(mood_times)

        recency_factor = min(1.0, recent_count / self.min_samples_per_pattern)
        count_factor = min(1.0, total_count / 10)

        return (recency_factor * 0.7) + (count_factor * 0.3)

    def _predict_pattern(
        self,
        pattern_key: str,
        timestamp: float,
    ) -> Dict[str, Any]:
        """Predict pattern occurrence from time-based history."""
        patterns = self.time_patterns.get(pattern_key, {})
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day_of_week = dt.weekday()

        hour_times = patterns.get(hour, [])
        day_times = patterns.get(f"day_{day_of_week}", [])

        total_samples = len(hour_times) + len(day_times)

        if total_samples < self.min_samples_per_pattern:
            return {
                "predicted": False,
                "confidence": 0.0,
                "details": {
                    "samples": total_samples,
                    "min_required": self.min_samples_per_pattern,
                },
            }

        hour_confidence = self._calculate_time_confidence(hour_times)
        day_confidence = self._calculate_time_confidence(day_times)

        # Weighted blend
        confidence = 0.6 * hour_confidence + 0.4 * day_confidence

        self.pattern_confidence[pattern_key] = confidence

        return {
            "predicted": confidence >= self.confidence_threshold,
            "confidence": confidence,
            "details": {
                "samples": total_samples,
                "hour_samples": len(hour_times),
                "day_samples": len(day_times),
                "hour_confidence": hour_confidence,
                "day_confidence": day_confidence,
            },
        }

    @staticmethod
    def _calculate_time_confidence(times: List[float]) -> float:
        """
        Calculate confidence based on recent timing consistency.

        Uses variance of the last 7 days of timestamps to assess how
        regular the pattern is.
        """
        if not times:
            return 0.0

        now = time.time()
        recent_times = [t for t in times if t > now - (7 * 24 * 3600)]

        if not recent_times:
            return 0.0

        times_array = np.array(recent_times)
        variance = float(np.var(times_array))

        if variance < 3600:  # < 1h variance
            return 0.9
        elif variance < 7200:  # < 2h
            return 0.7
        elif variance < 14400:  # < 4h
            return 0.5
        else:
            return 0.3

    # ------------------------------------------------------------------
    # Sequence prediction
    # ------------------------------------------------------------------

    def predict_sequence(
        self,
        start_device: str,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Predict device sequence based on learned A->B chains.

        Args:
            start_device: Starting device of the chain.
            timestamp: Epoch seconds (unused, kept for API compat).

        Returns:
            Sequence prediction with ``predicted``, ``sequence``,
            ``confidence``, ``occurrences``, ``total_sequences``.
        """
        if not self.enabled or not self._is_initialized:
            return {"predicted": False, "sequence": [], "confidence": 0.0}

        sequences = self.sequence_patterns.get(start_device, [])

        if not sequences:
            return {"predicted": False, "sequence": [], "confidence": 0.0}

        # Find the most common sequence
        sequence_counts: Dict[tuple, int] = Counter(
            tuple(seq) for seq in sequences
        )
        most_common_seq, most_common_count = sequence_counts.most_common(1)[0]

        confidence = most_common_count / len(sequences)

        return {
            "predicted": confidence >= self.confidence_threshold,
            "sequence": list(most_common_seq),
            "confidence": confidence,
            "occurrences": most_common_count,
            "total_sequences": len(sequences),
        }

    # ------------------------------------------------------------------
    # Summary / reset
    # ------------------------------------------------------------------

    def get_habit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of detected habits within a time window.

        Args:
            hours: Lookback window in hours.

        Returns:
            Dict with device_patterns, time_patterns, mood_patterns,
            sequences, and totals.
        """
        cutoff = time.time() - (hours * 3600)

        device_events: Dict[str, Any] = {}
        for device_id, events in self.device_patterns.items():
            recent_events = [e for e in events if e["timestamp"] >= cutoff]
            device_events[device_id] = {
                "count": len(recent_events),
                "event_types": list({e["event_type"] for e in recent_events}),
            }

        mood_summary: Dict[str, Dict[str, int]] = {}
        for pattern_key, mood_data in self.mood_patterns.items():
            mood_summary[pattern_key] = {
                mood: len(ts) for mood, ts in mood_data.items()
            }

        return {
            "device_patterns": device_events,
            "total_patterns": len(self.device_patterns),
            "time_patterns": {k: len(v) for k, v in self.time_patterns.items()},
            "mood_patterns": mood_summary,
            "sequences": {k: len(v) for k, v in self.sequence_patterns.items()},
        }

    def reset(self) -> None:
        """Reset the predictor state (clears all learned patterns)."""
        self.device_patterns.clear()
        self.sequence_patterns.clear()
        self.time_patterns.clear()
        self.mood_patterns.clear()
        self.pattern_confidence.clear()
        self.last_prediction_time.clear()
        self._is_initialized = False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, filename: str = "habit_predictor.json") -> None:
        """
        Persist current state to disk.

        Args:
            filename: Name of the JSON file inside ``self.storage_path``.
        """
        path = Path(self.storage_path)
        path.mkdir(parents=True, exist_ok=True)
        filepath = path / filename

        # Convert defaultdicts to plain dicts for JSON serialisation
        state = {
            "device_patterns": dict(self.device_patterns),
            "sequence_patterns": dict(self.sequence_patterns),
            "time_patterns": {
                k: {str(tk): tv for tk, tv in v.items()}
                for k, v in self.time_patterns.items()
            },
            "mood_patterns": {
                k: dict(v) for k, v in self.mood_patterns.items()
            },
            "pattern_confidence": dict(self.pattern_confidence),
            "is_initialized": self._is_initialized,
        }

        try:
            filepath.write_text(json.dumps(state, indent=2))
            logger.info("Habit predictor state saved to %s", filepath)
        except OSError as exc:
            logger.warning("Failed to save habit predictor state: %s", exc)

    def load(self, filename: str = "habit_predictor.json") -> bool:
        """
        Load persisted state from disk.

        Args:
            filename: Name of the JSON file inside ``self.storage_path``.

        Returns:
            True if state was loaded successfully, False otherwise.
        """
        filepath = Path(self.storage_path) / filename

        if not filepath.exists():
            logger.info("No persisted state at %s", filepath)
            return False

        try:
            state = json.loads(filepath.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load habit predictor state: %s", exc)
            return False

        # Restore device_patterns
        self.device_patterns = defaultdict(list, state.get("device_patterns", {}))

        # Restore sequence_patterns
        self.sequence_patterns = defaultdict(list, state.get("sequence_patterns", {}))

        # Restore time_patterns (keys may be int-like strings)
        tp_raw = state.get("time_patterns", {})
        self.time_patterns = defaultdict(lambda: defaultdict(list))
        for pk, tp_dict in tp_raw.items():
            for tk, tv in tp_dict.items():
                # Restore int keys where possible (hour slots)
                try:
                    restored_key: Any = int(tk)
                except ValueError:
                    restored_key = tk
                self.time_patterns[pk][restored_key] = tv

        # Restore mood_patterns
        mp_raw = state.get("mood_patterns", {})
        self.mood_patterns = defaultdict(lambda: defaultdict(list))
        for pk, mp_dict in mp_raw.items():
            for mk, mv in mp_dict.items():
                self.mood_patterns[pk][mk] = mv

        self.pattern_confidence = state.get("pattern_confidence", {})
        self._is_initialized = state.get("is_initialized", False)

        logger.info("Habit predictor state loaded from %s", filepath)
        return True


class ContextAwareHabitPredictor(HabitPredictor):
    """
    Extended habit predictor with multi-user and mood awareness.

    Tracks separate patterns per user and provides personalised
    habit predictions.  Inherits all base capabilities (time patterns,
    mood patterns, sequence learning) and adds:

    - Per-user device event tracking
    - Per-user sequence tracking
    - User-specific prediction with confidence scoring
    - Cross-user summary
    """

    def __init__(self, **kwargs: Any):
        """Initialize context-aware habit predictor."""
        super().__init__(**kwargs)
        self.user_patterns: Dict[str, Dict[str, List[float]]] = {}
        self.user_sequences: Dict[str, List[List[str]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # User-specific observation
    # ------------------------------------------------------------------

    def observe_user(
        self,
        user_id: str,
        device_id: str,
        event_type: str,
        timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Observe a user-specific device event.

        Also feeds the base predictor so global patterns are updated.

        Args:
            user_id: ID of the user.
            device_id: ID of the device.
            event_type: Type of event.
            timestamp: Epoch seconds when the event occurred.
            context: Additional context (mood, device_chain, ...).
        """
        if not self.enabled:
            return

        ts = timestamp or time.time()

        # Track user-specific pattern
        pattern_key = f"{user_id}_{device_id}_{event_type}"
        self.user_patterns.setdefault(user_id, {}).setdefault(
            pattern_key, []
        ).append(ts)

        # Track user-specific sequences
        if context and context.get("device_chain"):
            self.user_sequences[user_id].append(context["device_chain"][:10])

        # Feed global predictor
        self.observe(
            device_id=device_id,
            event_type=event_type,
            timestamp=ts,
            context=context,
        )

    # ------------------------------------------------------------------
    # User-specific prediction
    # ------------------------------------------------------------------

    def predict_for_user(
        self,
        user_id: str,
        device_id: str,
        event_type: str,
        timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Predict pattern for a specific user.

        Blends user-specific confidence with the global prediction to
        provide a personalised score.

        Args:
            user_id: ID of the user.
            device_id: ID of the device.
            event_type: Type of event to predict.
            timestamp: Epoch seconds for the prediction window.
            context: Optional context (mood, ...).

        Returns:
            User-specific prediction dict.
        """
        if user_id not in self.user_patterns:
            return {
                "predicted": False,
                "confidence": 0.0,
                "details": {"user": user_id, "reason": "no_data"},
            }

        pattern_key = f"{user_id}_{device_id}_{event_type}"

        if pattern_key not in self.user_patterns[user_id]:
            return {
                "predicted": False,
                "confidence": 0.0,
                "details": {"user": user_id, "reason": "no_pattern"},
            }

        pattern_times = self.user_patterns[user_id][pattern_key]

        if len(pattern_times) < self.min_samples_per_pattern:
            return {
                "predicted": False,
                "confidence": 0.0,
                "details": {
                    "user": user_id,
                    "pattern": pattern_key,
                    "samples": len(pattern_times),
                    "min_required": self.min_samples_per_pattern,
                },
            }

        # User-specific confidence (capped at 0.9)
        user_confidence = min(0.9, 0.5 + 0.1 * len(pattern_times))

        # Also get global prediction for blending
        global_pred = self.predict(
            device_id=device_id,
            event_type=event_type,
            timestamp=timestamp,
            context=context,
        )
        global_conf = global_pred.get("confidence", 0.0)

        # Blend: 60% user-specific, 40% global
        blended = (user_confidence * 0.6) + (global_conf * 0.4)

        return {
            "predicted": blended >= self.confidence_threshold,
            "confidence": blended,
            "details": {
                "user": user_id,
                "pattern": pattern_key,
                "samples": len(pattern_times),
                "user_confidence": user_confidence,
                "global_confidence": global_conf,
            },
        }

    # ------------------------------------------------------------------
    # User summary
    # ------------------------------------------------------------------

    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get habit summary for a specific user.

        Args:
            user_id: The user to summarise.

        Returns:
            Dict with patterns, sample counts, and sequences.
        """
        if user_id not in self.user_patterns:
            return {"user": user_id, "patterns": {}, "sequences": 0}

        patterns_summary = {
            pk: len(ts) for pk, ts in self.user_patterns[user_id].items()
        }

        return {
            "user": user_id,
            "patterns": patterns_summary,
            "total_observations": sum(patterns_summary.values()),
            "sequences": len(self.user_sequences.get(user_id, [])),
        }

    def list_users(self) -> List[str]:
        """Return list of tracked user IDs."""
        return list(self.user_patterns.keys())

    # ------------------------------------------------------------------
    # Persistence (extends base)
    # ------------------------------------------------------------------

    def save(self, filename: str = "habit_predictor.json") -> None:
        """Save state including user-specific data."""
        # Temporarily stash user data, let parent save base state
        super().save(filename)

        # Save user-specific state separately
        path = Path(self.storage_path)
        user_filepath = path / filename.replace(".json", "_users.json")

        user_state = {
            "user_patterns": self.user_patterns,
            "user_sequences": dict(self.user_sequences),
        }

        try:
            user_filepath.write_text(json.dumps(user_state, indent=2))
            logger.info("User habit state saved to %s", user_filepath)
        except OSError as exc:
            logger.warning("Failed to save user habit state: %s", exc)

    def load(self, filename: str = "habit_predictor.json") -> bool:
        """Load state including user-specific data."""
        base_loaded = super().load(filename)

        # Load user-specific state
        user_filepath = (
            Path(self.storage_path) / filename.replace(".json", "_users.json")
        )

        if user_filepath.exists():
            try:
                user_state = json.loads(user_filepath.read_text())
                self.user_patterns = user_state.get("user_patterns", {})
                self.user_sequences = defaultdict(
                    list, user_state.get("user_sequences", {})
                )
                logger.info("User habit state loaded from %s", user_filepath)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load user habit state: %s", exc)

        return base_loaded

    def reset(self) -> None:
        """Reset all state including user-specific data."""
        super().reset()
        self.user_patterns.clear()
        self.user_sequences.clear()
