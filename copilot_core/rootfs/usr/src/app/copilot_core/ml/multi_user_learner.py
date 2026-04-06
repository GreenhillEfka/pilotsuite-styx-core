"""Multi-User Behavior Learning Module - Learns preferences per user.

Migrated from pilotsuite-styx-ha
(custom_components/copilot_ha/ml/patterns/multi_user_learner.py)

Provides two classes:
- MultiUserLearner: Base learner with per-user preference tracking,
  presence detection, preference decay, user similarity scoring,
  and agglomerative user clustering.
- ContextAwareMultiUserLearner: Extends base with GPS co-location
  detection and location history tracking.
"""

import logging
import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)


class MultiUserLearner:
    """
    Learns and predicts behavior patterns for multiple users.

    Features:
    - Per-user preference learning with time-decay
    - User presence detection (arrive / leave events)
    - Device preference tracking per user
    - User preference similarity scoring (cosine-like)
    - Agglomerative user clustering
    """

    def __init__(
        self,
        min_samples_per_user: int = 5,
        preference_decay_hours: float = 168.0,  # 1 week
        similarity_threshold: float = 0.7,
        enabled: bool = True,
    ):
        """
        Initialize the multi-user learner.

        Args:
            min_samples_per_user: Minimum observations before predictions.
            preference_decay_hours: How long preferences persist (hours).
            similarity_threshold: Minimum similarity for user clustering.
            enabled: Whether the learner is active.
        """
        self.min_samples_per_user = min_samples_per_user
        self.preference_decay_hours = preference_decay_hours
        self.similarity_threshold = similarity_threshold
        self.enabled = enabled

        # Per-user data
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        self.user_behavior: Dict[str, List[Dict]] = defaultdict(list)
        self.user_presence: Dict[str, Dict[str, Any]] = {}

        # Agglomerative clustering
        self.user_clusters: Dict[str, List[str]] = defaultdict(list)
        self._cluster_ready = False

        self._is_initialized = False

    # ------------------------------------------------------------------
    # Event recording
    # ------------------------------------------------------------------

    def record_user_event(
        self,
        user_id: str,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Record an event for a specific user.

        Args:
            user_id: Unique identifier for the user.
            event_type: One of "arrive", "leave", "setting_change", etc.
            context: Event context (location, device, value, ...).
            timestamp: Unix epoch; defaults to now.
        """
        if not self.enabled:
            return

        if timestamp is None:
            timestamp = time.time()
        if context is None:
            context = {}

        event = {
            "event_type": event_type,
            "context": context,
            "timestamp": timestamp,
        }
        self.user_behavior[user_id].append(event)

        # Update presence tracking
        if event_type == "arrive":
            self.user_presence[user_id] = {
                "present": True,
                "location": context.get("location"),
                "timestamp": timestamp,
            }
        elif event_type == "leave":
            self.user_presence[user_id] = {
                "present": False,
                "last_location": context.get("location"),
                "timestamp": timestamp,
            }

        # Learn device preferences from setting changes
        if event_type == "setting_change":
            self._update_preference(user_id, context)

        self._is_initialized = True

    # ------------------------------------------------------------------
    # Preference tracking with decay
    # ------------------------------------------------------------------

    def _update_preference(
        self,
        user_id: str,
        context: Dict[str, Any],
    ) -> None:
        """Update user preferences from a setting_change event."""
        if "device" not in context or "value" not in context:
            return

        device = context["device"]
        value = context["value"]

        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {
                "settings": defaultdict(list),
                "created_at": time.time(),
            }

        preference = {
            "device": device,
            "value": value,
            "timestamp": time.time(),
        }
        self.user_preferences[user_id]["settings"][device].append(preference)

        # Prune preferences outside the decay window
        cutoff = time.time() - (self.preference_decay_hours * 3600)
        self.user_preferences[user_id]["settings"][device] = [
            p
            for p in self.user_preferences[user_id]["settings"][device]
            if p["timestamp"] >= cutoff
        ]

    def get_user_preference(
        self,
        user_id: str,
        device: str,
    ) -> Optional[float]:
        """
        Get most-recent preference value for a device.

        Args:
            user_id: Unique identifier for the user.
            device: Device identifier.

        Returns:
            Most recent preference value, or None.
        """
        if not self._is_initialized:
            return None
        if user_id not in self.user_preferences:
            return None

        user_prefs = self.user_preferences[user_id]
        if device not in user_prefs["settings"]:
            return None

        preferences = user_prefs["settings"][device]
        if not preferences:
            return None

        recent = sorted(preferences, key=lambda p: p["timestamp"], reverse=True)
        return recent[0]["value"]

    # ------------------------------------------------------------------
    # Presence / status
    # ------------------------------------------------------------------

    def get_user_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get current status for a user.

        Returns dict with keys: present, location, last_seen,
        activity_score (0-1), event_count.
        """
        presence = self.user_presence.get(user_id, {})

        behavior = self.user_behavior.get(user_id, [])
        if behavior:
            recent = [b for b in behavior if b["timestamp"] > time.time() - 3600]
            activity_score = min(1.0, len(recent) / 5)
        else:
            activity_score = 0.0

        return {
            "present": presence.get("present", False),
            "location": presence.get("location"),
            "last_seen": presence.get("timestamp"),
            "activity_score": activity_score,
            "event_count": len(behavior),
        }

    # ------------------------------------------------------------------
    # Similarity scoring
    # ------------------------------------------------------------------

    def find_similar_users(
        self,
        user_id: str,
    ) -> List[Tuple[str, float]]:
        """
        Find users with similar device-preference patterns.

        Args:
            user_id: Reference user.

        Returns:
            List of (other_user_id, similarity_score) sorted descending,
            filtered by similarity_threshold.
        """
        if user_id not in self.user_preferences:
            return []

        user_prefs = self.user_preferences[user_id]
        if not user_prefs.get("settings"):
            return []

        similar_users = []
        for other_id, other_prefs in self.user_preferences.items():
            if other_id == user_id or not other_prefs.get("settings"):
                continue

            similarity = self._calculate_similarity(
                user_prefs["settings"],
                other_prefs["settings"],
            )
            if similarity >= self.similarity_threshold:
                similar_users.append((other_id, similarity))

        return sorted(similar_users, key=lambda x: x[1], reverse=True)

    def _calculate_similarity(
        self,
        settings1: Dict[str, List],
        settings2: Dict[str, List],
    ) -> float:
        """Calculate mean per-device similarity between two users' settings.

        For each shared device the similarity is
        ``1 - |mean1 - mean2| / range`` where range is the combined
        value range (floored to 1.0 to avoid division by zero).
        """
        all_devices = set(settings1.keys()) | set(settings2.keys())
        if not all_devices:
            return 0.0

        similarities: List[float] = []

        for device in all_devices:
            prefs1 = settings1.get(device, [])
            prefs2 = settings2.get(device, [])
            if not prefs1 or not prefs2:
                continue

            values1 = [p["value"] for p in prefs1]
            values2 = [p["value"] for p in prefs2]

            mean1 = sum(values1) / len(values1)
            mean2 = sum(values2) / len(values2)

            all_values = values1 + values2
            max_val = max(all_values)
            min_val = min(all_values)
            range_val = max_val - min_val if max_val != min_val else 1.0

            diff = abs(mean1 - mean2) / range_val
            similarity = 1 - min(1.0, diff)
            similarities.append(similarity)

        if not similarities:
            return 0.0

        return sum(similarities) / len(similarities)

    # ------------------------------------------------------------------
    # Agglomerative clustering
    # ------------------------------------------------------------------

    def get_cluster_for_user(self, user_id: str) -> Optional[str]:
        """
        Get the cluster ID for a user.

        Lazily builds clusters on first access.
        """
        if not self._cluster_ready:
            self._build_clusters()

        for cluster_id, members in self.user_clusters.items():
            if user_id in members:
                return cluster_id
        return None

    def _build_clusters(self) -> None:
        """Build user clusters via single-link agglomerative merging."""
        if len(self.user_preferences) < 2:
            return

        # Each user starts in its own cluster
        for user_id in self.user_preferences:
            self.user_clusters[f"cluster_{user_id}"] = [user_id]

        merged = True
        while merged:
            merged = False
            cluster_ids = list(self.user_clusters.keys())

            for i, cluster1 in enumerate(cluster_ids):
                for cluster2 in cluster_ids[i + 1:]:
                    if cluster2 not in self.user_clusters:
                        continue  # already merged away

                    users1 = self.user_clusters[cluster1]
                    users2 = self.user_clusters[cluster2]

                    for u1 in users1:
                        for u2 in users2:
                            similarity = self._calculate_user_cluster_similarity(
                                u1, u2
                            )
                            if similarity >= self.similarity_threshold:
                                self.user_clusters[cluster1] = users1 + users2
                                del self.user_clusters[cluster2]
                                merged = True
                                break
                        if merged:
                            break
                if merged:
                    break

        self._cluster_ready = True

    def _calculate_user_cluster_similarity(
        self,
        user1: str,
        user2: str,
    ) -> float:
        """Calculate preference similarity between two users."""
        if user1 not in self.user_preferences or user2 not in self.user_preferences:
            return 0.0
        return self._calculate_similarity(
            self.user_preferences[user1]["settings"],
            self.user_preferences[user2]["settings"],
        )

    # ------------------------------------------------------------------
    # Summary / reporting
    # ------------------------------------------------------------------

    def get_multi_user_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of multi-user behavior over *hours*.

        Returns dict with total_users, present_users, user_summaries,
        and clusters.
        """
        cutoff = time.time() - (hours * 3600)

        user_summaries: Dict[str, Any] = {}
        for user_id, behavior in self.user_behavior.items():
            recent = [b for b in behavior if b["timestamp"] >= cutoff]
            if not recent:
                continue

            event_types: Dict[str, int] = defaultdict(int)
            for event in recent:
                event_types[event["event_type"]] += 1

            user_summaries[user_id] = {
                "event_count": len(recent),
                "event_types": dict(event_types),
                "present": (
                    user_id in self.user_presence
                    and self.user_presence[user_id].get("present", False)
                ),
            }

        return {
            "total_users": len(user_summaries),
            "present_users": sum(
                1 for s in user_summaries.values() if s["present"]
            ),
            "user_summaries": user_summaries,
            "clusters": dict(self.user_clusters),
        }

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all learner state."""
        self.user_preferences.clear()
        self.user_behavior.clear()
        self.user_presence.clear()
        self.user_clusters.clear()
        self._cluster_ready = False
        self._is_initialized = False


# ======================================================================
# Context-Aware Extension
# ======================================================================


class ContextAwareMultiUserLearner(MultiUserLearner):
    """
    Extended multi-user learner with spatial context awareness.

    Adds GPS location tracking and co-location detection on top
    of the base learner's preference and clustering logic.
    """

    def __init__(
        self,
        spatial_threshold_meters: float = 10.0,
        **kwargs: Any,
    ):
        """
        Initialize context-aware multi-user learner.

        Args:
            spatial_threshold_meters: Max distance (m) to consider
                two users "at the same location".
            **kwargs: Forwarded to MultiUserLearner.__init__.
        """
        super().__init__(**kwargs)
        self.spatial_threshold = spatial_threshold_meters
        self.location_history: Dict[str, List[Dict]] = defaultdict(list)
        self.shared_preferences: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Location tracking
    # ------------------------------------------------------------------

    def record_location(
        self,
        user_id: str,
        latitude: float,
        longitude: float,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Record a GPS location for a user.

        Args:
            user_id: Unique identifier for the user.
            latitude: GPS latitude.
            longitude: GPS longitude.
            timestamp: Unix epoch; defaults to now.
        """
        if timestamp is None:
            timestamp = time.time()

        self.location_history[user_id].append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "timestamp": timestamp,
            }
        )

    def get_user_location(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent recorded location for a user.

        Returns:
            Location dict (latitude, longitude, timestamp), or None.
        """
        history = self.location_history.get(user_id)
        if not history:
            return None

        return max(history, key=lambda x: x["timestamp"])

    # ------------------------------------------------------------------
    # Co-location detection
    # ------------------------------------------------------------------

    def are_users_together(
        self,
        user_ids: List[str],
        time_window_minutes: int = 10,
    ) -> bool:
        """
        Check if all listed users are at the same location.

        Uses the Haversine formula for distance calculation.

        Args:
            user_ids: List of user IDs to check.
            time_window_minutes: Only consider locations recorded
                within this many minutes.

        Returns:
            True if every pair of users is within
            *spatial_threshold* meters of each other.
        """
        if len(user_ids) < 2:
            return False

        cutoff = time.time() - (time_window_minutes * 60)

        # Collect most-recent location per user within the window
        recent_locations: Dict[str, Dict] = {}
        for user_id in user_ids:
            history = self.location_history.get(user_id, [])
            recent = [loc for loc in history if loc["timestamp"] >= cutoff]
            if recent:
                recent_locations[user_id] = max(
                    recent, key=lambda x: x["timestamp"]
                )

        if len(recent_locations) < 2:
            return False

        # All-pairs distance check
        locations = list(recent_locations.values())
        for i, loc1 in enumerate(locations):
            for loc2 in locations[i + 1 :]:
                distance = self._haversine_distance(
                    loc1["latitude"],
                    loc1["longitude"],
                    loc2["latitude"],
                    loc2["longitude"],
                )
                if distance > self.spatial_threshold:
                    return False

        return True

    # ------------------------------------------------------------------
    # Distance calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate the great-circle distance in meters between two
        GPS coordinates using the Haversine formula.

        Args:
            lat1, lon1: First point (decimal degrees).
            lat2, lon2: Second point (decimal degrees).

        Returns:
            Distance in meters.
        """
        R = 6_371_000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


# Slice 70: Learning Progress Visualization API (P3-004)
def get_learning_progress(self, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get learning progress for a user or all users.
    
    Returns metrics on how well the model knows each user's preferences.
    """
    def user_stats(uid: str) -> Dict[str, Any]:
        prefs = self.user_preferences.get(uid, {})
        events = self.user_behavior.get(uid, [])
        clusters = [k for k, v in self.user_clusters.items() if uid in v]
        learned_devices = len([k for k, v in prefs.items() if v.get('count', 0) >= self.min_samples_per_user])
        total_devices = len(prefs)
        confidence = learned_devices / max(total_devices, 1)
        
        # Decay factor
        last_ts = max((e.get('timestamp', 0) for e in events), default=0)
        age_hours = (time.time() - last_ts) / 3600 if last_ts else self.preference_decay_hours
        freshness = max(0.0, 1.0 - age_hours / self.preference_decay_hours)
        
        return {
            "user_id": uid,
            "total_events": len(events),
            "learned_devices": learned_devices,
            "total_devices": total_devices,
            "confidence_score": round(confidence, 3),
            "preference_freshness": round(freshness, 3),
            "clusters": clusters,
            "last_activity_hours_ago": round(age_hours, 1),
        }
    
    if user_id:
        return user_stats(user_id)
    return {uid: user_stats(uid) for uid in self.user_preferences}


def get_learning_history(self, user_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get learning history for a user over N days."""
    cutoff = time.time() - days * 86400
    events = [
        e for e in self.user_behavior.get(user_id, [])
        if e.get('timestamp', 0) >= cutoff
    ]
    # Group by day
    by_day = defaultdict(list)
    for e in events:
        import datetime
        day = datetime.datetime.fromtimestamp(e.get('timestamp', 0)).strftime('%Y-%m-%d')
        by_day[day].append(e)
    return [
        {"date": day, "events": len(evs), "types": list(set(e.get('event_type', '') for e in evs))}
        for day, evs in sorted(by_day.items())
    ]
