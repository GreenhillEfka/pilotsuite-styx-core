"""Mood-aware calendar scheduling.

Integrates mood state detection with calendar management to provide
context-aware scheduling recommendations and automatic adjustments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from copilot_core.mood.engine import MoodState, MoodResult
from copilot_core.calendar.smart_scheduler import (
    SmartScheduler,
    SmartSchedulerConfig,
    ScheduleRecommendation,
    EventType,
    EventPriority,
)

logger = logging.getLogger(__name__)


@dataclass
class MoodCalendarConfig:
    """Configuration for mood-aware calendar scheduling."""
    
    # Mood-based scheduling rules
    avoid_meetings_during_stress: bool = True
    prefer_breaks_on_low_mood: bool = True
    schedule_focus_when_calm: bool = True
    
    # Thresholds
    stress_threshold: float = 0.7
    low_energy_threshold: float = 0.3
    high_energy_threshold: float = 0.7
    
    # Auto-adjustment settings
    auto_reschedule_low_priority: bool = False
    suggest_breaks_after_meetings: bool = True
    break_duration_minutes: int = 10
    
    # Lighting integration
    adjust_lighting_for_meetings: bool = True
    adjust_lighting_for_focus: bool = True
    
    # HA integration
    ha_calendar_entity: Optional[str] = None
    mood_sensor_entity: Optional[str] = None


@dataclass
class MoodAdjustedEvent:
    """Event with mood-based adjustments."""
    
    original_event: Dict[str, Any]
    adjusted_start: Optional[datetime] = None
    adjusted_end: Optional[datetime] = None
    mood_at_scheduling: Optional[str] = None
    lighting_scene: Optional[str] = None
    break_suggested: bool = False
    adjustment_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.original_event.get("summary"),
            "original_start": self.original_event.get("start", {}).get("dateTime"),
            "adjusted_start": self.adjusted_start.isoformat() if self.adjusted_start else None,
            "adjusted_end": self.adjusted_end.isoformat() if self.adjusted_end else None,
            "mood_at_scheduling": self.mood_at_scheduling,
            "lighting_scene": self.lighting_scene,
            "break_suggested": self.break_suggested,
            "adjustment_reason": self.adjustment_reason,
        }


class MoodAwareScheduler:
    """Mood-aware calendar scheduler.
    
    Extends SmartScheduler with mood-based adjustments and
    Home Assistant lighting scene integration.
    """
    
    def __init__(
        self,
        config: Optional[MoodCalendarConfig] = None,
        smart_scheduler: Optional[SmartScheduler] = None,
    ):
        self.config = config or MoodCalendarConfig()
        self.scheduler = smart_scheduler or SmartScheduler()
        self._current_mood: Optional[MoodResult] = None
        self._mood_cache_ts: float = 0.0
    
    def set_current_mood(self, mood_result: MoodResult) -> None:
        """Set the current mood state for scheduling decisions."""
        self._current_mood = mood_result
        self._mood_cache_ts = datetime.now(timezone.utc).timestamp()
    
    def _get_current_mood(self) -> Optional[MoodResult]:
        """Get current mood, fetching if necessary."""
        # Cache mood for 5 minutes
        if self._current_mood and (datetime.now(timezone.utc).timestamp() - self._mood_cache_ts) < 300:
            return self._current_mood
        
        # Try to fetch from HA
        try:
            mood_state = self._fetch_mood_from_ha()
            if mood_state:
                self._current_mood = mood_state
                self._mood_cache_ts = datetime.now(timezone.utc).timestamp()
        except Exception as exc:
            logger.debug("Could not fetch mood: %s", exc)
        
        return self._current_mood
    
    def _fetch_mood_from_ha(self) -> Optional[MoodResult]:
        """Fetch current mood state from Home Assistant."""
        import os
        import requests as http_requests
        
        if not self.config.mood_sensor_entity:
            return None
        
        ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
        headers = {"Authorization": f"Bearer {ha_token}"}
        
        try:
            resp = http_requests.get(
                f"{ha_url}/states/{self.config.mood_sensor_entity}",
                headers=headers,
                timeout=5,
            )
            
            if resp.ok:
                data = resp.json()
                state = data.get("state", "neutral")
                attributes = data.get("attributes", {})
                
                # Map HA state to MoodState
                mood_map = {
                    "away": MoodState.AWAY,
                    "night": MoodState.NIGHT,
                    "relax": MoodState.RELAX,
                    "focus": MoodState.FOCUS,
                    "active": MoodState.ACTIVE,
                    "neutral": MoodState.NEUTRAL,
                }
                
                mood_state = mood_map.get(state.lower(), MoodState.NEUTRAL)
                
                return MoodResult(
                    mood=mood_state,
                    confidence=attributes.get("confidence", 0.5),
                    reasons=attributes.get("reasons", []),
                    features=type('obj', (object,), {
                        'stress_index': attributes.get("stress_index", 0.0),
                        'comfort_index': attributes.get("comfort_index", 0.5),
                        'energy_level': attributes.get("energy_level", 0.5),
                    })(),
                    timestamp=datetime.now(timezone.utc),
                )
        except Exception as exc:
            logger.debug("Failed to fetch mood from HA: %s", exc)
        
        return None
    
    def _get_mood_state(self) -> Optional[MoodState]:
        """Extract MoodState from current mood."""
        mood = self._get_current_mood()
        return mood.mood if mood else None
    
    def _get_energy_level(self) -> float:
        """Extract energy level from current mood."""
        mood = self._get_current_mood()
        if mood and hasattr(mood.features, 'energy_level'):
            return mood.features.energy_level
        return 0.5
    
    def _get_stress_level(self) -> float:
        """Extract stress level from current mood."""
        mood = self._get_current_mood()
        if mood and hasattr(mood.features, 'stress_index'):
            return mood.features.stress_index
        return 0.0
    
    def recommend_with_mood(
        self,
        duration_minutes: int,
        event_type: EventType = EventType.TASK,
        priority: EventPriority = EventPriority.MEDIUM,
        look_ahead_days: int = 3,
    ) -> ScheduleRecommendation:
        """Get scheduling recommendation with mood awareness."""
        
        mood_state = self._get_mood_state()
        energy_level = self._get_energy_level()
        stress_level = self._get_stress_level()
        
        # Adjust event type based on mood
        adjusted_event_type = event_type
        
        if self.config.avoid_meetings_during_stress and stress_level > self.config.stress_threshold:
            if event_type == EventType.MEETING and priority != EventPriority.HIGH:
                logger.info("High stress detected - suggesting break instead of meeting")
                adjusted_event_type = EventType.BREAK
        
        if self.config.prefer_breaks_on_low_mood and energy_level < self.config.low_energy_threshold:
            if event_type == EventType.TASK and priority != EventPriority.HIGH:
                logger.info("Low energy detected - suggesting break")
                adjusted_event_type = EventType.BREAK
        
        if self.config.schedule_focus_when_calm and mood_state == MoodState.FOCUS:
            if event_type == EventType.TASK:
                logger.info("Focus mood detected - optimal for deep work")
        
        # Get recommendation from base scheduler
        recommendation = self.scheduler.recommend_slot(
            duration_minutes=duration_minutes,
            event_type=adjusted_event_type,
            priority=priority,
            mood_state=mood_state,
            energy_level=energy_level,
            look_ahead_days=look_ahead_days,
        )
        
        # Add mood-specific reasons
        if adjusted_event_type != event_type:
            recommendation.reasons.append(
                f"Event type adjusted from {event_type.value} to {adjusted_event_type.value} based on mood"
            )
        
        if stress_level > self.config.stress_threshold:
            recommendation.reasons.append(f"High stress level detected: {stress_level:.2f}")
        
        if energy_level < self.config.low_energy_threshold:
            recommendation.reasons.append(f"Low energy level detected: {energy_level:.2f}")
        
        return recommendation
    
    def adjust_event_for_mood(self, event: Dict[str, Any]) -> MoodAdjustedEvent:
        """Adjust an existing event based on current mood."""
        
        adjusted = MoodAdjustedEvent(original_event=event)
        
        mood = self._get_current_mood()
        if not mood:
            return adjusted
        
        adjusted.mood_at_scheduling = mood.mood.value
        
        event_start_str = event.get("start", {}).get("dateTime", "")
        if not event_start_str:
            return adjusted
        
        try:
            event_start = datetime.fromisoformat(event_start_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return adjusted
        
        hour = event_start.hour
        
        # Determine lighting scene based on event type and mood
        if self.config.adjust_lighting_for_meetings:
            summary = event.get("summary", "").lower()
            
            if "meeting" in summary or "call" in summary or "gespräch" in summary:
                if mood.mood == MoodState.FOCUS:
                    adjusted.lighting_scene = "meeting_focus"
                elif mood.mood == MoodState.STRESS:
                    adjusted.lighting_scene = "meeting_calm"
                else:
                    adjusted.lighting_scene = "meeting_default"
            
            elif "lunch" in summary or "mittag" in summary:
                adjusted.lighting_scene = "relax_warm"
            
            elif mood.mood == MoodState.FOCUS:
                if self.config.adjust_lighting_for_focus:
                    adjusted.lighting_scene = "focus_cool"
        
        # Suggest break after meetings if stressed
        if self.config.suggest_breaks_after_meetings:
            if mood.features.stress_index > self.config.stress_threshold:
                summary = event.get("summary", "").lower()
                if "meeting" in summary or "call" in summary:
                    adjusted.break_suggested = True
                    adjusted.adjustment_reason = "Break suggested due to elevated stress"
        
        # Check if rescheduling is needed
        if self.config.auto_reschedule_low_priority:
            stress_level = mood.features.stress_index
            energy_level = mood.features.energy_level
            
            priority_str = event.get("priority", "medium").lower()
            is_low_priority = priority_str == "low" or "optional" in event.get("summary", "").lower()
            
            if is_low_priority and stress_level > self.config.stress_threshold:
                # Find better slot
                duration = 30  # Default duration
                new_recommendation = self.recommend_with_mood(
                    duration_minutes=duration,
                    event_type=EventType.TASK,
                    priority=EventPriority.LOW,
                )
                
                if new_recommendation.confidence > 0.7:
                    adjusted.adjusted_start = new_recommendation.recommended_start
                    adjusted.adjusted_end = new_recommendation.recommended_end
                    adjusted.adjustment_reason = "Rescheduled due to high stress"
        
        return adjusted
    
    def get_mood_calendar_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Get calendar summary with mood insights."""
        
        import os
        import requests as http_requests
        
        ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
        headers = {"Authorization": f"Bearer {ha_token}"}
        
        events = []
        try:
            resp = http_requests.get(f"{ha_url}/states", headers=headers, timeout=10)
            if resp.ok:
                calendars = [
                    s["entity_id"]
                    for s in resp.json()
                    if s.get("entity_id", "").startswith("calendar.")
                ]
                
                for cal_id in calendars:
                    try:
                        resp = http_requests.get(
                            f"{ha_url}/calendars/{cal_id}",
                            params={
                                "start": start_date.isoformat(),
                                "end": end_date.isoformat(),
                            },
                            headers=headers,
                            timeout=10,
                        )
                        if resp.ok:
                            events.extend(resp.json())
                    except Exception as exc:
                        logger.debug("Failed to fetch calendar events: %s", exc)
        except Exception as exc:
            logger.warning("Failed to fetch events: %s", exc)
        
        # Analyze events with mood context
        mood = self._get_current_mood()
        mood_state = mood.mood if mood else MoodState.NEUTRAL
        energy_level = mood.features.energy_level if mood else 0.5
        stress_level = mood.features.stress_index if mood else 0.0
        
        # Categorize events
        meetings = []
        focus_blocks = []
        breaks = []
        
        for event in events:
            summary = event.get("summary", "").lower()
            
            if any(kw in summary for kw in ["meeting", "call", "gespräch", "termin"]):
                meetings.append(event)
            elif any(kw in summary for kw in ["focus", "deep work", "konzentration"]):
                focus_blocks.append(event)
            elif any(kw in summary for kw in ["break", "pause", "lunch", "mittag"]):
                breaks.append(event)
        
        # Generate insights
        insights = []
        
        if len(meetings) > 5 and stress_level > 0.5:
            insights.append({
                "type": "warning",
                "message": "Viele Meetings bei erhöhtem Stresslevel — plane Pufferzeiten ein.",
            })
        
        if len(focus_blocks) == 0 and energy_level > 0.6:
            insights.append({
                "type": "suggestion",
                "message": "Gute Energie — ideal für Fokus-Blöcke.",
            })
        
        if len(breaks) == 0 and len(meetings) > 3:
            insights.append({
                "type": "suggestion",
                "message": "Keine Pausen geplant — vergiss nicht, Pausen einzulegen.",
            })
        
        if mood_state == MoodState.STRESS and len(meetings) > 2:
            insights.append({
                "type": "alert",
                "message": "Stresslevel erhöht bei mehreren Meetings — erwäge Umplanung.",
            })
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "current_mood": mood_state.value if mood else "unknown",
            "energy_level": round(energy_level, 3),
            "stress_level": round(stress_level, 3),
            "event_counts": {
                "total": len(events),
                "meetings": len(meetings),
                "focus_blocks": len(focus_blocks),
                "breaks": len(breaks),
            },
            "insights": insights,
        }
    
    def create_lighting_automation(
        self,
        event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Create lighting automation for an event based on mood."""
        
        adjusted = self.adjust_event_for_mood(event)
        
        if not adjusted.lighting_scene:
            return None
        
        event_start_str = event.get("start", {}).get("dateTime", "")
        if not event_start_str:
            return None
        
        try:
            event_start = datetime.fromisoformat(event_start_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        
        # Define lighting scenes
        scenes = {
            "meeting_focus": {
                "scene": "scene.focus_meeting",
                "brightness": 80,
                "color_temp": 400,  # Cool white
            },
            "meeting_calm": {
                "scene": "scene.calm_meeting",
                "brightness": 60,
                "color_temp": 350,  # Neutral
            },
            "meeting_default": {
                "scene": "scene.default_meeting",
                "brightness": 70,
                "color_temp": 370,
            },
            "relax_warm": {
                "scene": "scene.relax",
                "brightness": 50,
                "color_temp": 250,  # Warm
            },
            "focus_cool": {
                "scene": "scene.deep_focus",
                "brightness": 85,
                "color_temp": 450,  # Very cool
            },
        }
        
        scene_config = scenes.get(adjusted.lighting_scene)
        if not scene_config:
            return None
        
        return {
            "trigger": {
                "platform": "time",
                "at": event_start.strftime("%H:%M:%S"),
            },
            "action": {
                "service": "light.turn_on",
                "data": {
                    "brightness_pct": scene_config["brightness"],
                    "color_temp": scene_config["color_temp"],
                },
                "target": {
                    "area_id": ["office", "living_room"],  # Configurable
                },
            },
            "metadata": {
                "event_summary": event.get("summary"),
                "mood_at_creation": adjusted.mood_at_scheduling,
                "lighting_scene": adjusted.lighting_scene,
            },
        }
    
    def get_proactive_suggestions(
        self,
        look_ahead_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get proactive scheduling suggestions based on mood and calendar."""
        
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(hours=look_ahead_hours)
        
        summary = self.get_mood_calendar_summary(now, end_date)
        suggestions = []
        
        mood = self._get_current_mood()
        if not mood:
            return suggestions
        
        # Suggestion: Take break if stressed
        if mood.features.stress_index > self.config.stress_threshold:
            suggestions.append({
                "type": "break",
                "priority": "high",
                "title": "Pause empfohlen",
                "message": "Dein Stresslevel ist erhöht. Eine kurze Pause könnte helfen.",
                "action": {
                    "type": "schedule_break",
                    "duration_minutes": self.config.break_duration_minutes,
                },
            })
        
        # Suggestion: Focus time if energy is high
        if mood.features.energy_level > self.config.high_energy_threshold:
            if summary["event_counts"]["focus_blocks"] == 0:
                suggestions.append({
                    "type": "focus",
                    "priority": "medium",
                    "title": "Gute Energie für Fokus-Arbeit",
                    "message": "Dein Energieniveau ist hoch — ideal für konzentrierte Aufgaben.",
                    "action": {
                        "type": "schedule_focus",
                        "duration_minutes": 90,
                    },
                })
        
        # Suggestion: Prepare for busy day
        if summary["event_counts"]["meetings"] > 4:
            suggestions.append({
                "type": "preparation",
                "priority": "medium",
                "title": "Voller Tag ahead",
                "message": f"Du hast {summary['event_counts']['meetings']} Meetings geplant. Vergiss nicht, Pausen einzulegen.",
                "action": {
                    "type": "add_breaks",
                    "between_meetings": True,
                },
            })
        
        # Suggestion: Alarm adjustment for early meetings
        early_meetings = []
        for hour in range(6, 9):
            if summary["event_counts"].get("early_meetings", 0) > 0:
                early_meetings.append(hour)
        
        if early_meetings:
            suggestions.append({
                "type": "alarm",
                "priority": "high",
                "title": "Früher Termin morgen",
                "message": "Du hast morgen frühe Termine — soll ich den Wecker entsprechend stellen?",
                "action": {
                    "type": "adjust_alarm",
                    "minutes_earlier": 30,
                },
            })
        
        return suggestions
