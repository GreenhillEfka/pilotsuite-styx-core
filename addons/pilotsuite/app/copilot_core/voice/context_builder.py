"""Voice Context Builder for context-aware voice responses.

Builds comprehensive voice context including:
- Raum (Zone) context
- Tageszeit (Time of day) context
- Stimmung (Mood) context
- User preferences
- Active devices and activities
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..mood.engine import MoodEngine, MoodState, MoodConfig, MoodResult
from ..habitus.service import HabitusService

_LOGGER = logging.getLogger(__name__)


class TimeOfDay(str, Enum):
    """Time of day categories."""
    
    MORNING = "morning"  # 06:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 18:00
    EVENING = "evening"  # 18:00 - 23:00
    NIGHT = "night"  # 23:00 - 06:00


class DayType(str, Enum):
    """Day type categories."""
    
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


@dataclass
class TimeContext:
    """Time-based context for voice responses."""
    
    time_of_day: TimeOfDay = TimeOfDay.AFTERNOON
    day_type: DayType = DayType.WEEKDAY
    hour: int = 0
    minute: int = 0
    is_quiet_hours: bool = False
    is_typical_activity_time: bool = True
    
    # Human-readable descriptions (DE/EN)
    description_de: str = ""
    description_en: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_of_day": self.time_of_day.value,
            "day_type": self.day_type.value,
            "hour": self.hour,
            "minute": self.minute,
            "is_quiet_hours": self.is_quiet_hours,
            "is_typical_activity_time": self.is_typical_activity_time,
            "description_de": self.description_de,
            "description_en": self.description_en,
        }


@dataclass
class ZoneContext:
    """Zone/room context for voice responses."""
    
    zone_name: str = "unknown"
    zone_type: str = "living_room"  # living_room, bedroom, kitchen, office, bathroom
    is_occupied: bool = False
    occupancy_confidence: float = 0.0
    
    # Zone-specific settings
    default_mood: MoodState = MoodState.NEUTRAL
    typical_activities: List[str] = field(default_factory=list)
    
    # Related entities
    light_entities: List[str] = field(default_factory=list)
    climate_entities: List[str] = field(default_factory=list)
    media_entities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "is_occupied": self.is_occupied,
            "occupancy_confidence": self.occupancy_confidence,
            "default_mood": self.default_mood.value,
            "typical_activities": self.typical_activities,
            "light_entities": self.light_entities,
            "climate_entities": self.climate_entities,
            "media_entities": self.media_entities,
        }


@dataclass
class DeviceContext:
    """Active device context."""
    
    device_name: str = ""
    device_type: str = ""  # light, climate, media, sensor
    state: str = "unknown"  # on, off, playing, paused, etc.
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_name": self.device_name,
            "device_type": self.device_type,
            "state": self.state,
            "attributes": self.attributes,
        }


@dataclass
class VoiceContext:
    """Comprehensive voice context for personalized responses."""
    
    # Mood context
    mood_state: Optional[MoodState] = None
    mood_confidence: float = 0.0
    mood_reasons: List[str] = field(default_factory=list)
    
    # Time context
    time_context: Optional[TimeContext] = None
    
    # Zone context
    current_zone: Optional[ZoneContext] = None
    zone_name: str = "unknown"
    
    # Device context
    active_devices: List[DeviceContext] = field(default_factory=list)
    recent_actions: List[str] = field(default_factory=list)
    
    # User context
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    language_preference: str = "de"
    
    # Habitus patterns
    relevant_patterns: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    timestamp: str = ""
    context_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood": {
                "state": self.mood_state.value if self.mood_state else None,
                "confidence": self.mood_confidence,
                "reasons": self.mood_reasons,
            },
            "time": self.time_context.to_dict() if self.time_context else None,
            "zone": self.current_zone.to_dict() if self.current_zone else None,
            "zone_name": self.zone_name,
            "active_devices": [d.to_dict() for d in self.active_devices],
            "recent_actions": self.recent_actions,
            "user_preferences": self.user_preferences,
            "language_preference": self.language_preference,
            "relevant_patterns": self.relevant_patterns,
            "timestamp": self.timestamp,
            "context_version": self.context_version,
        }


@dataclass(frozen=True)
class VoiceContextRuntime:
    """Narrow runtime dependency bundle for voice-context enrichment."""

    mood_engine: Optional[MoodEngine] = None
    habitus_service: Optional[HabitusService] = None


class VoiceContextBuilder:
    """Builds comprehensive voice context from multiple sources.
    
    Integration points:
    - Mood Engine: Current mood state and confidence
    - Habitus Service: Pattern-based context
    - Home Assistant: Zone, device, and occupancy data
    - User preferences: Language, tone preferences
    """
    
    # Zone type mappings
    ZONE_TYPE_MAP = {
        "wohnzimmer": "living_room",
        "wohnzimmer_h": "living_room",
        "schlafzimmer": "bedroom",
        "schlafzimmer_h": "bedroom",
        "kueche": "kitchen",
        "küche": "kitchen",
        "buero": "office",
        "büro": "office",
        "arbeitszimmer": "office",
        "bad": "bathroom",
        "badezimmer": "bathroom",
        "flur": "hallway",
        "diele": "hallway",
        "gaeste_wc": "bathroom",
        "keller": "utility",
        "garage": "utility",
        "garten": "outdoor",
        "terrasse": "outdoor",
        "balkon": "outdoor",
    }
    
    # Typical activities per zone type
    ZONE_ACTIVITIES = {
        "living_room": ["relaxen", "fernsehen", "musik hören", "besuch empfangen"],
        "bedroom": ["schlafen", "lesen", "entspannen"],
        "kitchen": ["kochen", "essen", "abwaschen"],
        "office": ["arbeiten", "konzentrieren", "telefonieren"],
        "bathroom": ["baden", "duschen", "fertig machen"],
        "hallway": ["durchgehen", "ankommen", "verlassen"],
        "utility": ["waschen", "aufräumen", "lagern"],
        "outdoor": ["draußen sein", "grillen", "entspannen"],
    }
    
    # Quiet hours configuration
    QUIET_HOURS_START = 22  # 22:00
    QUIET_HOURS_END = 7  # 07:00
    
    def __init__(self):
        """Initialize context builder."""
        self._cache: Dict[str, VoiceContext] = {}
        self._cache_ttl_seconds = 60  # 1 minute cache

    @staticmethod
    def _resolve_language_preference(user_preferences: Optional[Dict[str, Any]]) -> str:
        """Resolve language preference from replayed user preferences."""
        if not isinstance(user_preferences, dict):
            return "de"

        language = user_preferences.get("language") or user_preferences.get("preferred_language")
        if isinstance(language, str) and language:
            return language.lower()

        return "de"
    
    def build_context(
        self,
        mood_engine: Optional[MoodEngine] = None,
        habitus_service: Optional[HabitusService] = None,
        zone_name: Optional[str] = None,
        sensor_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        active_devices: Optional[List[Dict[str, Any]]] = None,
        context_runtime: Optional[VoiceContextRuntime] = None,
        force_refresh: bool = False,
    ) -> VoiceContext:
        """Build comprehensive voice context.
        
        Args:
            mood_engine: Mood engine for mood state
            habitus_service: Habitus service for pattern context
            zone_name: Current zone (auto-detected if None)
            sensor_data: Current sensor data from HA
            user_preferences: User preferences (language, etc.)
            context_runtime: Narrow runtime dependency bundle for mood/pattern sources
            force_refresh: Force fresh context (skip cache)
            
        Returns:
            VoiceContext with all context data
        """
        # Request-replayed data must not bleed across zone-cached contexts.
        has_replayed_inputs = (
            sensor_data is not None or user_preferences is not None or active_devices is not None
        )
        cache_key = f"voice_context:{zone_name or 'global'}"
        use_cache = not force_refresh and not has_replayed_inputs
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            # Check if cache is still valid
            cache_age = (
                datetime.now(timezone.utc) - datetime.fromisoformat(cached.timestamp)
            ).total_seconds()
            if cache_age < self._cache_ttl_seconds:
                return cached

        if context_runtime is not None:
            mood_engine = context_runtime.mood_engine
            habitus_service = context_runtime.habitus_service

        now = datetime.now(timezone.utc)
        
        # Build time context
        time_context = self._build_time_context(now)
        
        # Build zone context
        zone_context = self._build_zone_context(zone_name, sensor_data)
        
        # Build mood context
        mood_state, mood_confidence, mood_reasons = self._build_mood_context(
            mood_engine,
            zone_name or zone_context.zone_name if zone_context else "wohnzimmer",
            sensor_data,
        )
        
        # Build device context — use replay data if provided, otherwise build from sensor_data
        if active_devices is not None:
            device_contexts = []
            for d in active_devices:
                if isinstance(d, dict):
                    device_contexts.append(DeviceContext(
                        device_name=d.get("device_name", ""),
                        device_type=d.get("device_type", ""),
                        state=d.get("state", "unknown"),
                        attributes=d.get("attributes", {}),
                    ))
            active_devices_out = device_contexts
        else:
            active_devices_out = self._build_device_context(sensor_data)

        # Get relevant habitus patterns
        relevant_patterns = self._get_relevant_patterns(
            habitus_service,
            zone_name or zone_context.zone_name if zone_context else "wohnzimmer",
        )
        
        # Determine language preference
        language = self._resolve_language_preference(user_preferences)
        
        # Build final context
        context = VoiceContext(
            mood_state=mood_state,
            mood_confidence=mood_confidence,
            mood_reasons=mood_reasons,
            time_context=time_context,
            current_zone=zone_context,
            zone_name=zone_name or zone_context.zone_name if zone_context else "unknown",
            active_devices=active_devices_out,
            recent_actions=self._get_recent_actions(),
            user_preferences=user_preferences or {},
            language_preference=language,
            relevant_patterns=relevant_patterns,
            timestamp=now.isoformat(),
            context_version="1.0",
        )
        
        # Cache only runtime-built contexts. Replayed request context stays per-request.
        if not has_replayed_inputs:
            self._cache[cache_key] = context
        
        return context
    
    def _build_time_context(self, now: datetime) -> TimeContext:
        """Build time-based context."""
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()  # 0 = Monday, 6 = Sunday
        
        # Determine time of day
        if 6 <= hour < 12:
            time_of_day = TimeOfDay.MORNING
            desc_de = "Guten Morgen"
            desc_en = "Good morning"
        elif 12 <= hour < 18:
            time_of_day = TimeOfDay.AFTERNOON
            desc_de = "Guten Tag"
            desc_en = "Good afternoon"
        elif 18 <= hour < 23:
            time_of_day = TimeOfDay.EVENING
            desc_de = "Guten Abend"
            desc_en = "Good evening"
        else:
            time_of_day = TimeOfDay.NIGHT
            desc_de = "Gute Nacht"
            desc_en = "Good night"
        
        # Determine day type
        if weekday >= 5:  # Saturday or Sunday
            day_type = DayType.WEEKEND
        else:
            day_type = DayType.WEEKDAY
        
        # Check quiet hours
        is_quiet_hours = hour >= self.QUIET_HOURS_START or hour < self.QUIET_HOURS_END
        
        # Determine if this is typical activity time
        is_typical_activity_time = not is_quiet_hours and time_of_day != TimeOfDay.NIGHT
        
        return TimeContext(
            time_of_day=time_of_day,
            day_type=day_type,
            hour=hour,
            minute=minute,
            is_quiet_hours=is_quiet_hours,
            is_typical_activity_time=is_typical_activity_time,
            description_de=desc_de,
            description_en=desc_en,
        )
    
    def _build_zone_context(
        self,
        zone_name: Optional[str],
        sensor_data: Optional[Dict[str, Any]],
    ) -> ZoneContext:
        """Build zone context from zone name and sensor data."""
        zone_name = zone_name or "wohnzimmer"
        
        # Map zone name to zone type
        zone_type = self.ZONE_TYPE_MAP.get(zone_name.lower(), "living_room")
        
        # Get typical activities for this zone type
        typical_activities = self.ZONE_ACTIVITIES.get(zone_type, [])
        
        # Determine occupancy from sensor data
        is_occupied = False
        occupancy_confidence = 0.0
        
        if sensor_data:
            # Check for motion sensors in zone
            motion_entities = [
                k for k in sensor_data.keys()
                if "motion" in k.lower() and zone_name.lower() in k.lower()
            ]
            
            for entity in motion_entities:
                state = sensor_data.get(entity, {}).get("state", "")
                if state in ("on", "True", True, 1):
                    is_occupied = True
                    occupancy_confidence = max(occupancy_confidence, 0.8)
            
            # Check for presence sensors
            presence_entities = [
                k for k in sensor_data.keys()
                if "presence" in k.lower() or "person" in k.lower()
            ]
            
            for entity in presence_entities:
                state = sensor_data.get(entity, {}).get("state", "")
                if state in ("home", "on", "True", True, 1):
                    is_occupied = True
                    occupancy_confidence = max(occupancy_confidence, 0.9)
        
        # Determine default mood for zone
        default_mood = MoodState.NEUTRAL
        if zone_type == "bedroom":
            default_mood = MoodState.NIGHT
        elif zone_type == "office":
            default_mood = MoodState.FOCUS
        elif zone_type == "living_room":
            default_mood = MoodState.RELAX
        
        # Get related entities
        light_entities = [
            k for k in (sensor_data or {}).keys()
            if k.startswith("light.") and zone_name.lower() in k.lower()
        ]
        climate_entities = [
            k for k in (sensor_data or {}).keys()
            if k.startswith("climate.") and zone_name.lower() in k.lower()
        ]
        media_entities = [
            k for k in (sensor_data or {}).keys()
            if k.startswith("media_player.") and zone_name.lower() in k.lower()
        ]
        
        return ZoneContext(
            zone_name=zone_name,
            zone_type=zone_type,
            is_occupied=is_occupied,
            occupancy_confidence=occupancy_confidence,
            default_mood=default_mood,
            typical_activities=typical_activities,
            light_entities=light_entities,
            climate_entities=climate_entities,
            media_entities=media_entities,
        )
    
    def _build_mood_context(
        self,
        mood_engine: Optional[MoodEngine],
        zone_name: str,
        sensor_data: Optional[Dict[str, Any]],
    ) -> tuple[Optional[MoodState], float, List[str]]:
        """Build mood context from mood engine."""
        if mood_engine is None:
            return MoodState.NEUTRAL, 0.5, ["Mood engine not available"]
        
        try:
            # Get mood result from engine
            mood_result = mood_engine.get_zone_mood(zone_name)
            
            if mood_result is None:
                # Try to infer mood from sensor data
                if sensor_data:
                    # Simple heuristic: motion + light = active, dark + no motion = night
                    has_motion = any(
                        "motion" in k.lower() and v.get("state") in ("on", "True", True, 1)
                        for k, v in sensor_data.items()
                    )
                    is_dark = any(
                        "illuminance" in k.lower() and float(v.get("state", 100)) < 40
                        for k, v in sensor_data.items()
                        if v.get("state")
                    )
                    
                    if is_dark and not has_motion:
                        return MoodState.NIGHT, 0.6, ["Dark environment, no motion"]
                    elif has_motion:
                        return MoodState.ACTIVE, 0.5, ["Motion detected"]
                
                return MoodState.NEUTRAL, 0.5, ["No mood data available"]
            
            return (
                mood_result.mood,
                mood_result.confidence,
                mood_result.reasons,
            )
        
        except Exception as e:
            _LOGGER.warning("Failed to get mood context: %s", e)
            return MoodState.NEUTRAL, 0.5, [f"Error: {str(e)}"]
    
    def _build_device_context(
        self,
        sensor_data: Optional[Dict[str, Any]],
    ) -> List[DeviceContext]:
        """Build device context from sensor data."""
        devices = []
        
        if not sensor_data:
            return devices
        
        for entity_id, state_data in sensor_data.items():
            if not isinstance(state_data, dict):
                continue
            
            state = state_data.get("state", "unknown")
            
            # Only include active/interesting devices
            if state in ("off", "unavailable", "unknown"):
                continue
            
            # Parse entity type
            if "." in entity_id:
                domain, name = entity_id.split(".", 1)
            else:
                domain = "sensor"
                name = entity_id
            
            # Create device context
            device = DeviceContext(
                device_name=name,
                device_type=domain,
                state=state,
                attributes=state_data.get("attributes", {}),
            )
            devices.append(device)
        
        return devices[:10]  # Limit to 10 devices
    
    def _get_relevant_patterns(
        self,
        habitus_service: Optional[HabitusService],
        zone_name: str,
    ) -> List[Dict[str, Any]]:
        """Get relevant habitus patterns for context."""
        if habitus_service is None:
            return []
        
        try:
            # Get recent patterns
            patterns = habitus_service.list_recent_patterns(limit=5)
            
            # Filter for zone-relevant patterns
            relevant = []
            for pattern in patterns:
                metadata = pattern.get("metadata", {})
                pattern_zone = metadata.get("zone_filter")
                
                if pattern_zone == zone_name or pattern_zone is None:
                    relevant.append(pattern)
            
            return relevant[:3]  # Limit to 3 patterns
        
        except Exception as e:
            _LOGGER.debug("Failed to get habitus patterns: %s", e)
            return []
    
    def _get_recent_actions(self, limit: int = 5) -> List[str]:
        """Get recent actions from the event ingest store."""
        try:
            from copilot_core.ingest.event_store import get_recent_events
            events = get_recent_events(limit=limit)
            actions = []
            for ev in events:
                entity_id = ev.get("entity_id", "")
                new_state = ev.get("attributes", {}).get("new_state", "")
                domain = ev.get("attributes", {}).get("domain", "")
                if entity_id and new_state:
                    actions.append(f"{domain}.{entity_id} → {new_state}")
            return actions
        except Exception as exc:
            _LOGGER.debug("Could not fetch recent actions: %s", exc)
            return []
    
    def clear_cache(self):
        """Clear context cache."""
        self._cache.clear()
    
    def get_cached_context(self, zone_name: str = "global") -> Optional[VoiceContext]:
        """Get cached context for a zone."""
        cache_key = f"voice_context:{zone_name}"
        return self._cache.get(cache_key)
