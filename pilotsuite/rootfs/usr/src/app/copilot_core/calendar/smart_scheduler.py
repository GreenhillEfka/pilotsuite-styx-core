"""Smart Scheduling Engine for PilotSuite.

Provides intelligent calendar event scheduling with mood awareness,
energy optimization, and habitus-based recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import requests as http_requests

from copilot_core.mood.engine import MoodState

logger = logging.getLogger(__name__)


class EventPriority(str, Enum):
    """Event priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    """Event type classification."""
    MEETING = "meeting"
    TASK = "task"
    BREAK = "break"
    SOCIAL = "social"
    HEALTH = "health"
    MAINTENANCE = "maintenance"
    CUSTOM = "custom"


@dataclass
class ScheduleRecommendation:
    """Recommendation for scheduling an event."""
    
    recommended_start: datetime
    recommended_end: datetime
    confidence: float
    reasons: List[str]
    alternative_slots: List[Tuple[datetime, datetime]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    mood_impact: Optional[str] = None
    energy_impact: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended_start": self.recommended_start.isoformat(),
            "recommended_end": self.recommended_end.isoformat(),
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "alternative_slots": [
                (s.isoformat(), e.isoformat()) for s, e in self.alternative_slots
            ],
            "conflicts": self.conflicts,
            "mood_impact": self.mood_impact,
            "energy_impact": round(self.energy_impact, 3) if self.energy_impact else None,
        }


@dataclass
class SmartSchedulerConfig:
    """Configuration for the smart scheduler."""
    
    # Working hours
    work_start_hour: int = 8
    work_end_hour: int = 18
    
    # Break configuration
    break_duration_minutes: int = 15
    break_interval_minutes: int = 90
    lunch_start_hour: int = 12
    lunch_end_hour: int = 14
    lunch_duration_minutes: int = 60
    
    # Buffer times
    meeting_buffer_minutes: int = 5
    focus_block_min_minutes: int = 60
    
    # Mood-aware settings
    respect_mood_states: bool = True
    avoid_focus_during_stress: bool = True
    prefer_breaks_on_low_energy: bool = True
    
    # Energy optimization
    energy_aware: bool = True
    peak_energy_hours: Tuple[int, int] = (9, 12)  # Morning peak
    
    # Constraints
    max_meetings_per_day: int = 6
    max_consecutive_meetings: int = 3


class SmartScheduler:
    """Smart scheduling engine with mood and energy awareness."""
    
    def __init__(self, config: Optional[SmartSchedulerConfig] = None):
        self.config = config or SmartSchedulerConfig()
        self._event_cache: Dict[str, List[Dict]] = {}
        self._cache_ts: float = 0.0
        
    def _get_ha_headers(self) -> Tuple[str, Dict]:
        """Get Home Assistant API headers."""
        import os
        ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        return ha_url, headers
    
    def _fetch_calendar_events(self, start: str, end: str) -> List[Dict]:
        """Fetch events from all HA calendars."""
        ha_url, headers = self._get_ha_headers()
        
        try:
            resp = http_requests.get(f"{ha_url}/states", headers=headers, timeout=10)
            if not resp.ok:
                return []
            
            calendars = [
                s["entity_id"]
                for s in resp.json()
                if s.get("entity_id", "").startswith("calendar.")
            ]
            
            all_events = []
            for cal_id in calendars:
                try:
                    resp = http_requests.get(
                        f"{ha_url}/calendars/{cal_id}",
                        params={"start": start, "end": end},
                        headers=headers,
                        timeout=10,
                    )
                    if resp.ok:
                        events = resp.json()
                        for ev in events:
                            ev["calendar_entity_id"] = cal_id
                        all_events.extend(events)
                except Exception as exc:
                    logger.debug("Failed to fetch events from %s: %s", cal_id, exc)
            
            all_events.sort(key=lambda e: e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")))
            return all_events
            
        except Exception as exc:
            logger.warning("Failed to fetch calendar events: %s", exc)
            return []
    
    def _parse_event_time(self, event: Dict) -> Tuple[datetime, datetime]:
        """Parse event start and end times."""
        start_data = event.get("start", {})
        end_data = event.get("end", {})
        
        start_str = start_data.get("dateTime", start_data.get("date", ""))
        end_str = end_data.get("dateTime", end_data.get("date", ""))
        
        # Handle all-day events
        if "T" not in start_str:
            start = datetime.fromisoformat(start_str).replace(hour=0, minute=0, second=0)
            end = datetime.fromisoformat(end_str).replace(hour=23, minute=59, second=59)
        else:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        
        # Convert to local timezone if naive
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        return start, end
    
    def _get_day_events(self, date: datetime) -> List[Dict]:
        """Get all events for a specific day."""
        date_key = date.strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc)
        
        # Check cache
        if date_key in self._event_cache and (now.timestamp() - self._cache_ts) < 300:
            return self._event_cache[date_key]
        
        start = date.replace(hour=0, minute=0, second=0).isoformat()
        end = (date + timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
        
        events = self._fetch_calendar_events(start, end)
        self._event_cache[date_key] = events
        self._cache_ts = now.timestamp()
        
        return events
    
    def _find_free_slots(
        self,
        date: datetime,
        duration_minutes: int,
        existing_events: List[Dict],
        constraints: Optional[Dict] = None,
    ) -> List[Tuple[datetime, datetime]]:
        """Find available time slots on a given day."""
        
        work_start = date.replace(hour=self.config.work_start_hour, minute=0, second=0)
        work_end = date.replace(hour=self.config.work_end_hour, minute=0, second=0)
        
        # Build busy periods from existing events
        busy_periods = []
        for event in existing_events:
            start, end = self._parse_event_time(event)
            if start.date() == date.date():
                # Add buffer
                buffered_start = start - timedelta(minutes=self.config.meeting_buffer_minutes)
                buffered_end = end + timedelta(minutes=self.config.meeting_buffer_minutes)
                busy_periods.append((buffered_start, buffered_end))
        
        # Add lunch break if not already scheduled
        lunch_start = date.replace(hour=self.config.lunch_start_hour, minute=0, second=0)
        lunch_end = date.replace(hour=self.config.lunch_end_hour, minute=0, second=0)
        lunch_duration = timedelta(minutes=self.config.lunch_duration_minutes)
        
        has_lunch = any(
            s <= lunch_start and e >= lunch_end
            for s, e in busy_periods
        )
        
        if not has_lunch:
            busy_periods.append((lunch_start, lunch_start + lunch_duration))
        
        # Sort busy periods
        busy_periods.sort(key=lambda x: x[0])
        
        # Find free slots
        free_slots = []
        current_time = work_start
        duration = timedelta(minutes=duration_minutes)
        
        for busy_start, busy_end in busy_periods:
            if current_time < busy_start:
                slot_end = min(busy_start, work_end)
                if slot_end - current_time >= duration:
                    free_slots.append((current_time, slot_end))
            
            current_time = max(current_time, busy_end)
        
        # Check remaining time after last busy period
        if current_time < work_end and work_end - current_time >= duration:
            free_slots.append((current_time, work_end))
        
        return free_slots
    
    def _score_time_slot(
        self,
        slot_start: datetime,
        slot_end: datetime,
        event_type: EventType,
        mood_state: Optional[MoodState] = None,
        energy_level: float = 0.5,
    ) -> float:
        """Score a time slot based on various factors."""
        
        score = 0.5  # Base score
        
        hour = slot_start.hour
        
        # Energy-based scoring
        if self.config.energy_aware:
            peak_start, peak_end = self.config.peak_energy_hours
            if peak_start <= hour <= peak_end:
                # Morning peak - good for focus tasks
                if event_type == EventType.TASK:
                    score += 0.2
                elif event_type == EventType.MEETING:
                    score += 0.1
            elif hour >= 14 and hour <= 16:
                # Afternoon slump
                if event_type == EventType.BREAK:
                    score += 0.2
                elif event_type == EventType.TASK:
                    score -= 0.1
        
        # Mood-based scoring
        if self.config.respect_mood_states and mood_state:
            if mood_state == MoodState.STRESS and self.config.avoid_focus_during_stress:
                if event_type == EventType.TASK:
                    score -= 0.3
                elif event_type == EventType.BREAK:
                    score += 0.3
            
            if mood_state == MoodState.RELAX:
                if event_type == EventType.SOCIAL:
                    score += 0.2
                elif event_type == EventType.MEETING:
                    score -= 0.1
        
        # Late day penalty for important tasks
        if hour >= 17 and event_type in (EventType.TASK, EventType.MEETING):
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def recommend_slot(
        self,
        duration_minutes: int,
        event_type: EventType = EventType.TASK,
        priority: EventPriority = EventPriority.MEDIUM,
        preferred_date: Optional[datetime] = None,
        mood_state: Optional[MoodState] = None,
        energy_level: float = 0.5,
        look_ahead_days: int = 3,
    ) -> ScheduleRecommendation:
        """Recommend the best time slot for an event."""
        
        now = datetime.now(timezone.utc)
        start_date = preferred_date or now
        
        reasons = []
        best_slot: Optional[Tuple[datetime, datetime]] = None
        best_score = 0.0
        all_conflicts: List[Dict] = []
        alternatives: List[Tuple[datetime, datetime]] = []
        
        # Search through days
        for day_offset in range(look_ahead_days):
            current_date = (start_date + timedelta(days=day_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            events = self._get_day_events(current_date)
            free_slots = self._find_free_slots(current_date, duration_minutes, events)
            
            for slot_start, slot_end in free_slots:
                score = self._score_time_slot(
                    slot_start, slot_end, event_type, mood_state, energy_level
                )
                
                slot_info = {
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "date": current_date.strftime("%Y-%m-%d"),
                    "score": score,
                }
                
                if score > best_score:
                    best_score = score
                    best_slot = (slot_start, slot_end)
                    reasons = self._generate_reasons(slot_start, event_type, mood_state, energy_level)
                else:
                    alternatives.append((slot_start, slot_end))
        
        # Check for conflicts
        if best_slot:
            events = self._get_day_events(best_slot[0])
            for event in events:
                ev_start, ev_end = self._parse_event_time(event)
                if (best_slot[0] < ev_end and best_slot[1] > ev_start):
                    all_conflicts.append({
                        "summary": event.get("summary", "Unknown"),
                        "start": ev_start.isoformat(),
                        "end": ev_end.isoformat(),
                    })
        
        # Fallback if no good slot found
        if not best_slot:
            # Schedule for next available morning
            next_day = (start_date + timedelta(days=look_ahead_days)).replace(
                hour=self.config.work_start_hour, minute=0, second=0
            )
            best_slot = (next_day, next_day + timedelta(minutes=duration_minutes))
            reasons = ["No optimal slots found - scheduled for next available morning"]
            best_score = 0.3
        
        # Calculate mood and energy impact
        mood_impact = None
        if mood_state and self.config.respect_mood_states:
            if best_score < 0.4:
                mood_impact = "suboptimal"
            elif best_score > 0.7:
                mood_impact = "positive"
        
        energy_impact = None
        if self.config.energy_aware:
            hour = best_slot[0].hour
            if self.config.peak_energy_hours[0] <= hour <= self.config.peak_energy_hours[1]:
                energy_impact = 0.2 if event_type == EventType.TASK else 0.0
            elif hour >= 14 and hour <= 16:
                energy_impact = -0.1
        
        return ScheduleRecommendation(
            recommended_start=best_slot[0],
            recommended_end=best_slot[1],
            confidence=best_score,
            reasons=reasons,
            alternative_slots=alternatives[:3],  # Top 3 alternatives
            conflicts=all_conflicts,
            mood_impact=mood_impact,
            energy_impact=energy_impact,
        )
    
    def _generate_reasons(
        self,
        slot_start: datetime,
        event_type: EventType,
        mood_state: Optional[MoodState],
        energy_level: float,
    ) -> List[str]:
        """Generate human-readable reasons for a recommendation."""
        
        reasons = []
        hour = slot_start.hour
        
        # Time-based reasons
        if 9 <= hour <= 11:
            reasons.append("Morning focus period - ideal for concentrated work")
        elif 12 <= hour <= 13:
            reasons.append("Post-lunch slot - good for lighter tasks")
        elif 14 <= hour <= 16:
            reasons.append("Afternoon slot - consider a break beforehand")
        elif hour >= 17:
            reasons.append("End of day - wrap up pending items")
        
        # Mood-based reasons
        if self.config.respect_mood_states and mood_state:
            if mood_state == MoodState.FOCUS:
                reasons.append("Current mood supports focused work")
            elif mood_state == MoodState.RELAX:
                if event_type == EventType.BREAK:
                    reasons.append("Good time for a restorative break")
            elif mood_state == MoodState.STRESS:
                if event_type == EventType.BREAK:
                    reasons.append("Break recommended to reduce stress")
        
        # Energy-based reasons
        if self.config.energy_aware:
            if energy_level < 0.3 and event_type != EventType.BREAK:
                reasons.append("Low energy detected - consider shorter duration")
            elif energy_level > 0.7:
                reasons.append("High energy - good for challenging tasks")
        
        return reasons
    
    def get_day_summary(self, date: datetime) -> Dict[str, Any]:
        """Get a summary of the day's schedule."""
        
        events = self._get_day_events(date)
        
        total_meeting_time = timedelta(0)
        meeting_count = 0
        has_lunch = False
        busy_periods = []
        
        for event in events:
            start, end = self._parse_event_time(event)
            duration = end - start
            
            summary = event.get("summary", "").lower()
            
            if "lunch" in summary or "mittag" in summary:
                has_lunch = True
            
            if start.hour >= self.config.work_start_hour and start.hour < self.config.work_end_hour:
                meeting_count += 1
                total_meeting_time += duration
                busy_periods.append({
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "summary": event.get("summary"),
                })
        
        # Calculate free time
        work_duration = timedelta(hours=self.config.work_end_hour - self.config.work_start_hour)
        free_time = work_duration - total_meeting_time
        
        # Assess day density
        if meeting_count > self.config.max_meetings_per_day:
            density = "very_busy"
        elif meeting_count > self.config.max_meetings_per_day * 0.7:
            density = "busy"
        elif meeting_count > self.config.max_meetings_per_day * 0.4:
            density = "moderate"
        else:
            density = "light"
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "event_count": len(events),
            "meeting_count": meeting_count,
            "total_meeting_minutes": int(total_meeting_time.total_seconds() / 60),
            "free_time_minutes": int(free_time.total_seconds() / 60),
            "density": density,
            "has_lunch_break": has_lunch,
            "busy_periods": busy_periods,
            "recommendation": self._generate_day_recommendation(density, meeting_count, has_lunch),
        }
    
    def _generate_day_recommendation(
        self,
        density: str,
        meeting_count: int,
        has_lunch: bool,
    ) -> str:
        """Generate a recommendation for the day."""
        
        if density == "very_busy":
            if not has_lunch:
                return "Sehr voller Tag — plane eine Mittagspause ein!"
            return "Sehr voller Tag — plane Pufferzeiten zwischen Meetings."
        elif density == "busy":
            if not has_lunch:
                return "Voller Tag — vergiss nicht, eine Pause zu machen."
            return "Gut strukturierter Tag — behalte Pufferzeiten bei."
        elif density == "moderate":
            return "Ausgewogener Tag — gute Balance zwischen Meetings und Fokuszeit."
        else:
            return "Entspannter Tag — ideal für tiefgehende Aufgaben."
    
    def suggest_alarm_adjustment(self, next_day_events: List[Dict]) -> Optional[Dict]:
        """Suggest alarm clock adjustment based on next day's schedule."""
        
        if not next_day_events:
            return None
        
        # Find earliest event
        earliest_event = None
        for event in next_day_events:
            start, _ = self._parse_event_time(event)
            if start.hour < 12:  # Morning events only
                if earliest_event is None or start < earliest_event:
                    earliest_event = (event, start)
        
        if not earliest_event:
            return None
        
        event, event_start = earliest_event
        
        # Calculate suggested wake time (1 hour before + buffer)
        suggested_wake = event_start - timedelta(hours=1, minutes=15)
        
        # Check if this is earlier than usual
        usual_wake = datetime.now(timezone.utc).replace(
            hour=7, minute=0, second=0, microsecond=0
        )
        
        if suggested_wake < usual_wake:
            minutes_earlier = int((usual_wake - suggested_wake).total_seconds() / 60)
            
            return {
                "suggested_wake_time": suggested_wake.isoformat(),
                "minutes_earlier": minutes_earlier,
                "reason": f"Früher Termin: {event.get('summary', 'Unbekannt')} um {event_start.strftime('%H:%M')}",
                "message": f"Du hast morgen einen vollen Tag — soll ich den Wecker {minutes_earlier} Min früher stellen?",
            }
        
        return None
