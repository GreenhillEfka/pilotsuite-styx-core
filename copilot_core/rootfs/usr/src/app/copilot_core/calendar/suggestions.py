"""Proactive scheduling suggestions.

Generates intelligent suggestions for calendar optimization,
break reminders, and schedule adjustments based on mood, energy,
and existing calendar patterns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from copilot_core.mood.engine import MoodState, MoodResult
from copilot_core.calendar.smart_scheduler import SmartScheduler, EventType
from copilot_core.calendar.mood_aware import MoodAwareScheduler, MoodCalendarConfig

logger = logging.getLogger(__name__)


class SuggestionType(str, Enum):
    """Types of scheduling suggestions."""
    BREAK_REMINDER = "break_reminder"
    MEETING_PREP = "meeting_prep"
    SCHEDULE_OPTIMIZATION = "schedule_optimization"
    ALARM_ADJUSTMENT = "alarm_adjustment"
    LIGHTING_SCENE = "lighting_scene"
    FOCUS_BLOCK = "focus_block"
    BUFFER_TIME = "buffer_time"
    LUNCH_REMINDER = "lunch_reminder"
    END_OF_DAY_WRAP = "end_of_day_wrap"
    STRESS_RELIEF = "stress_relief"


class SuggestionPriority(str, Enum):
    """Priority levels for suggestions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ScheduleSuggestion:
    """A proactive scheduling suggestion."""
    
    suggestion_type: SuggestionType
    priority: SuggestionPriority
    title: str
    message: str
    action_type: Optional[str] = None
    action_params: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    related_event: Optional[Dict[str, Any]] = None
    mood_context: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.suggestion_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "action": {
                "type": self.action_type,
                "params": self.action_params,
            } if self.action_type else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "related_event": self.related_event,
            "mood_context": self.mood_context,
        }


@dataclass
class SuggestionConfig:
    """Configuration for suggestion generation."""
    
    # Break reminders
    break_reminder_interval_minutes: int = 90
    break_duration_minutes: int = 10
    min_breaks_per_day: int = 3
    
    # Meeting suggestions
    meeting_prep_minutes: int = 15
    buffer_between_meetings_minutes: int = 5
    max_consecutive_meetings: int = 3
    
    # Focus blocks
    min_focus_block_minutes: int = 60
    preferred_focus_hours: Tuple[int, int] = (9, 12)
    
    # Alarm adjustments
    alarm_adjustment_threshold_minutes: int = 30
    default_wake_hour: int = 7
    
    # End of day
    end_of_day_hour: int = 18
    wrap_up_minutes_before: int = 30
    
    # Mood-aware
    stress_break_threshold: float = 0.7
    energy_focus_threshold: float = 0.6
    
    # Lighting
    auto_lighting_scenes: bool = True
    
    # Quiet hours
    quiet_hours_start: int = 22
    quiet_hours_end: int = 7


class ScheduleSuggester:
    """Generates proactive scheduling suggestions."""
    
    def __init__(
        self,
        config: Optional[SuggestionConfig] = None,
        mood_aware_scheduler: Optional[MoodAwareScheduler] = None,
    ):
        self.config = config or SuggestionConfig()
        self.mood_scheduler = mood_aware_scheduler
        self._suggestion_history: List[ScheduleSuggestion] = []
        self._dismissed_suggestions: List[str] = []
    
    def _get_current_mood(self) -> Optional[MoodResult]:
        """Get current mood from mood scheduler."""
        if self.mood_scheduler:
            return self.mood_scheduler._get_current_mood()
        return None
    
    def _fetch_calendar_events(
        self,
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch calendar events from HA."""
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
                            params={"start": start.isoformat(), "end": end.isoformat()},
                            headers=headers,
                            timeout=10,
                        )
                        if resp.ok:
                            events.extend(resp.json())
                    except Exception as exc:
                        logger.debug("Failed to fetch calendar %s: %s", cal_id, exc)
        except Exception as exc:
            logger.warning("Failed to fetch events: %s", exc)
        
        return events
    
    def _parse_event_time(self, event: Dict) -> Tuple[datetime, datetime]:
        """Parse event start and end times."""
        start_data = event.get("start", {})
        end_data = event.get("end", {})
        
        start_str = start_data.get("dateTime", start_data.get("date", ""))
        end_str = end_data.get("dateTime", end_data.get("date", ""))
        
        if "T" not in start_str:
            start = datetime.fromisoformat(start_str).replace(hour=0, minute=0, second=0)
            end = datetime.fromisoformat(end_str).replace(hour=23, minute=59, second=59)
        else:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        return start, end
    
    def generate_break_reminders(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Generate break reminder suggestions."""
        
        now = now or datetime.now(timezone.utc)
        suggestions = []
        
        # Find last break
        last_break_time = None
        for event in events:
            summary = event.get("summary", "").lower()
            if any(kw in summary for kw in ["pause", "break", "lunch", "mittag"]):
                start, _ = self._parse_event_time(event)
                if start < now:
                    if last_break_time is None or start > last_break_time:
                        last_break_time = start
        
        # Check if break is due
        if last_break_time:
            minutes_since_break = (now - last_break_time).total_seconds() / 60
            if minutes_since_break >= self.config.break_reminder_interval_minutes:
                mood = self._get_current_mood()
                stress_level = mood.features.stress_index if mood else 0.0
                
                priority = SuggestionPriority.MEDIUM
                if stress_level > self.config.stress_break_threshold:
                    priority = SuggestionPriority.HIGH
                
                suggestions.append(ScheduleSuggestion(
                    suggestion_type=SuggestionType.BREAK_REMINDER,
                    priority=priority,
                    title="Zeit für eine Pause",
                    message=f"Du arbeitest seit {int(minutes_since_break)} Minuten ohne Pause.",
                    action_type="schedule_break",
                    action_params={
                        "duration_minutes": self.config.break_duration_minutes,
                        "type": "restorative" if stress_level > 0.5 else "active",
                    },
                    expires_at=now + timedelta(minutes=30),
                    mood_context=mood.mood.value if mood else None,
                ))
        
        # Check for consecutive meetings without breaks
        meeting_blocks = []
        current_block = []
        
        sorted_events = sorted(
            [e for e in events if self._is_meeting(e)],
            key=lambda e: e.get("start", {}).get("dateTime", "")
        )
        
        for event in sorted_events:
            start, end = self._parse_event_time(event)
            if start > now:
                if current_block and len(current_block) >= self.config.max_consecutive_meetings:
                    meeting_blocks.append(current_block)
                current_block = [event]
            elif current_block:
                # Check if this meeting connects to the block
                prev_start, prev_end = self._parse_event_time(current_block[-1])
                if abs((start - prev_end).total_seconds()) < 3600:  # Within 1 hour
                    current_block.append(event)
        
        # Suggest breaks between meeting blocks
        for block in meeting_blocks:
            if len(block) >= 2:
                last_meeting = block[-1]
                _, last_end = self._parse_event_time(last_meeting)
                
                if last_end > now:
                    break_time = last_end + timedelta(minutes=5)
                    suggestions.append(ScheduleSuggestion(
                        suggestion_type=SuggestionType.BUFFER_TIME,
                        priority=SuggestionPriority.MEDIUM,
                        title="Pufferzeit nach Meetings",
                        message=f"Nach {len(block)} Meetings empfiehlt sich eine kurze Pause.",
                        action_type="schedule_break",
                        action_params={
                            "duration_minutes": self.config.buffer_between_meetings_minutes,
                            "after_event": last_meeting.get("summary"),
                        },
                        related_event=last_meeting,
                        expires_at=break_time + timedelta(minutes=15),
                    ))
        
        return suggestions
    
    def generate_meeting_prep_suggestions(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Generate meeting preparation suggestions."""
        
        now = now or datetime.now(timezone.utc)
        suggestions = []
        
        for event in events:
            if not self._is_meeting(event):
                continue
            
            start, _ = self._parse_event_time(event)
            prep_time = start - timedelta(minutes=self.config.meeting_prep_minutes)
            
            time_until_prep = (prep_time - now).total_seconds()
            
            # Suggest prep 15 minutes before meeting
            if 0 < time_until_prep < 900:  # 0-15 minutes
                summary = event.get("summary", "Meeting")
                
                suggestions.append(ScheduleSuggestion(
                    suggestion_type=SuggestionType.MEETING_PREP,
                    priority=SuggestionPriority.MEDIUM,
                    title=f"Vorbereitung: {summary}",
                    message=f"Meeting in {self.config.meeting_prep_minutes} Minuten. Zeit für Vorbereitung.",
                    action_type="meeting_prep",
                    action_params={
                        "event_summary": summary,
                        "prep_minutes": self.config.meeting_prep_minutes,
                    },
                    related_event=event,
                    expires_at=start,
                ))
        
        return suggestions
    
    def generate_focus_block_suggestions(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Generate focus block suggestions."""
        
        now = now or datetime.now(timezone.utc)
        suggestions = []
        
        mood = self._get_current_mood()
        energy_level = mood.features.energy_level if mood else 0.5
        
        # Only suggest if energy is good
        if energy_level < self.config.energy_focus_threshold:
            return suggestions
        
        # Find free slots during preferred focus hours
        today_end = now.replace(hour=23, minute=59, second=59)
        free_slots = self._find_free_slots(events, now, today_end)
        
        for slot_start, slot_end in free_slots:
            hour = slot_start.hour
            duration_minutes = (slot_end - slot_start).total_seconds() / 60
            
            # Check if slot is during preferred focus hours
            if (self.config.preferred_focus_hours[0] <= hour <= self.config.preferred_focus_hours[1]
                and duration_minutes >= self.config.min_focus_block_minutes):
                
                suggestions.append(ScheduleSuggestion(
                    suggestion_type=SuggestionType.FOCUS_BLOCK,
                    priority=SuggestionPriority.MEDIUM,
                    title="Fokus-Zeit verfügbar",
                    message=f"Gute Energie — ideal für {int(duration_minutes)} Minuten konzentrierte Arbeit.",
                    action_type="schedule_focus",
                    action_params={
                        "start": slot_start.isoformat(),
                        "duration_minutes": min(duration_minutes, 90),
                        "energy_level": round(energy_level, 2),
                    },
                    expires_at=slot_start + timedelta(minutes=30),
                    mood_context=mood.mood.value if mood else None,
                ))
                break  # One suggestion per day
        
        return suggestions
    
    def generate_alarm_adjustment_suggestions(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Generate alarm adjustment suggestions for early meetings."""
        
        now = now or datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        tomorrow_end = tomorrow + timedelta(days=1)
        
        # Get tomorrow's events
        tomorrow_events = self._fetch_calendar_events(tomorrow.isoformat(), tomorrow_end.isoformat())
        
        # Find earliest morning event
        earliest_event = None
        earliest_time = None
        
        for event in tomorrow_events:
            start, _ = self._parse_event_time(event)
            if start.hour < 10:  # Morning events
                if earliest_time is None or start < earliest_time:
                    earliest_time = start
                    earliest_event = event
        
        if not earliest_event:
            return []
        
        # Calculate suggested wake time
        suggested_wake = earliest_time - timedelta(hours=1, minutes=15)
        usual_wake = tomorrow.replace(hour=self.config.default_wake_hour, minute=0)
        
        if suggested_wake < usual_wake:
            minutes_earlier = int((usual_wake - suggested_wake).total_seconds() / 60)
            
            if minutes_earlier >= self.config.alarm_adjustment_threshold_minutes:
                return [ScheduleSuggestion(
                    suggestion_type=SuggestionType.ALARM_ADJUSTMENT,
                    priority=SuggestionPriority.HIGH,
                    title="Früher Termin morgen",
                    message=f"Du hast morgen einen vollen Tag — soll ich den Wecker {minutes_earlier} Min früher stellen?",
                    action_type="adjust_alarm",
                    action_params={
                        "suggested_time": suggested_wake.strftime("%H:%M"),
                        "minutes_earlier": minutes_earlier,
                        "reason": earliest_event.get("summary", "Früher Termin"),
                        "event_time": earliest_time.strftime("%H:%M"),
                    },
                    related_event=earliest_event,
                    expires_at=tomorrow.replace(hour=22, minute=0),
                )]
        
        return []
    
    def generate_lighting_suggestions(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Generate lighting scene suggestions for events."""
        
        if not self.config.auto_lighting_scenes:
            return []
        
        now = now or datetime.now(timezone.utc)
        suggestions = []
        
        for event in events:
            start, _ = self._parse_event_time(event)
            
            if start > now and (start - now).total_seconds() < 7200:  # Next 2 hours
                summary = event.get("summary", "").lower()
                
                scene = None
                if any(kw in summary for kw in ["meeting", "call", "gespräch"]):
                    scene = "meeting_focus"
                elif any(kw in summary for kw in ["lunch", "mittag"]):
                    scene = "relax_warm"
                elif any(kw in summary for kw in ["focus", "deep work"]):
                    scene = "focus_cool"
                
                if scene:
                    suggestions.append(ScheduleSuggestion(
                        suggestion_type=SuggestionType.LIGHTING_SCENE,
                        priority=SuggestionPriority.LOW,
                        title=f"Lichtszene für: {event.get('summary', 'Event')}",
                        message=f"Automatische Lichtanpassung für '{event.get('summary')}'",
                        action_type="set_lighting_scene",
                        action_params={
                            "scene": scene,
                            "event_time": start.isoformat(),
                        },
                        related_event=event,
                        expires_at=start,
                    ))
        
        return suggestions
    
    def generate_stress_relief_suggestions(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Generate stress relief suggestions based on mood."""
        
        if now is None:
            now = datetime.now(timezone.utc)

        mood = self._get_current_mood()
        if not mood:
            return []

        stress_level = mood.features.stress_index

        if stress_level < self.config.stress_break_threshold:
            return []
        
        suggestions = []
        
        # High stress - suggest immediate break
        suggestions.append(ScheduleSuggestion(
            suggestion_type=SuggestionType.STRESS_RELIEF,
            priority=SuggestionPriority.HIGH,
            title="Stresslevel erhöht",
            message="Dein Stresslevel ist erhöht. Eine kurze Entspannungspause könnte helfen.",
            action_type="stress_relief",
            action_params={
                "type": "breathing_exercise",
                "duration_minutes": 5,
                "stress_level": round(stress_level, 2),
            },
            expires_at=now + timedelta(hours=1),
            mood_context=mood.mood.value,
        ))
        
        # Check if calendar is contributing to stress
        today_end = now.replace(hour=23, minute=59, second=59)
        today_events = [e for e in events if self._is_meeting(e)]
        
        if len(today_events) > 4:
            suggestions.append(ScheduleSuggestion(
                suggestion_type=SuggestionType.SCHEDULE_OPTIMIZATION,
                priority=SuggestionPriority.MEDIUM,
                title="Voller Tag — Umplanung möglich?",
                message=f"Du hast {len(today_events)} Meetings. Soll ich einige verschieben?",
                action_type="reschedule_optional",
                action_params={
                    "current_meetings": len(today_events),
                    "stress_level": round(stress_level, 2),
                },
                expires_at=today_end,
                mood_context=mood.mood.value,
            ))
        
        return suggestions
    
    def generate_lunch_reminder(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> Optional[ScheduleSuggestion]:
        """Generate lunch reminder if not scheduled."""
        
        now = now or datetime.now(timezone.utc)
        
        # Check if lunch is already scheduled
        has_lunch = False
        for event in events:
            summary = event.get("summary", "").lower()
            if "lunch" in summary or "mittag" in summary:
                start, _ = self._parse_event_time(event)
                if start.date() == now.date():
                    has_lunch = True
                    break
        
        if has_lunch:
            return None
        
        # Suggest lunch around noon
        lunch_time = now.replace(hour=12, minute=30, second=0)
        
        if now.hour < 13 and not has_lunch:
            return ScheduleSuggestion(
                suggestion_type=SuggestionType.LUNCH_REMINDER,
                priority=SuggestionPriority.MEDIUM,
                title="Mittagspause planen",
                message="Keine Mittagspause geplant — vergiss nicht, eine Pause zu machen.",
                action_type="schedule_lunch",
                action_params={
                    "suggested_time": lunch_time.isoformat(),
                    "duration_minutes": 45,
                },
                expires_at=now.replace(hour=14, minute=0),
            )
        
        return None
    
    def generate_end_of_day_suggestion(
        self,
        events: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> Optional[ScheduleSuggestion]:
        """Generate end-of-day wrap-up suggestion."""
        
        now = now or datetime.now(timezone.utc)
        
        wrap_time = now.replace(hour=self.config.end_of_day_hour) - timedelta(
            minutes=self.config.wrap_up_minutes_before
        )
        
        if abs((now - wrap_time).total_seconds()) < 1800:  # Within 30 min of wrap time
            # Check if there are unfinished tasks
            remaining_events = [
                e for e in events
                if self._parse_event_time(e)[0] > now
            ]
            
            if remaining_events:
                return ScheduleSuggestion(
                    suggestion_type=SuggestionType.END_OF_DAY_WRAP,
                    priority=SuggestionPriority.MEDIUM,
                    title="Feierabend-Vorbereitung",
                    message=f"Noch {len(remaining_events)} Termine heute. Zeit für Wrap-up.",
                    action_type="end_of_day_wrap",
                    action_params={
                        "remaining_events": len(remaining_events),
                        "wrap_time": wrap_time.isoformat(),
                    },
                    expires_at=now.replace(hour=self.config.end_of_day_hour),
                )
        
        return None
    
    def _is_meeting(self, event: Dict) -> bool:
        """Check if event is a meeting."""
        summary = event.get("summary", "").lower()
        return any(kw in summary for kw in [
            "meeting", "call", "gespräch", "termin", "appointment",
            "sync", "review", "planning"
        ])
    
    def _find_free_slots(
        self,
        events: List[Dict],
        start: datetime,
        end: datetime,
    ) -> List[Tuple[datetime, datetime]]:
        """Find free time slots between events."""
        
        busy_periods = []
        for event in events:
            event_start, event_end = self._parse_event_time(event)
            if event_start >= start and event_end <= end:
                busy_periods.append((event_start, event_end))
        
        busy_periods.sort(key=lambda x: x[0])
        
        free_slots = []
        current_time = start
        
        for busy_start, busy_end in busy_periods:
            if current_time < busy_start:
                free_slots.append((current_time, busy_start))
            current_time = max(current_time, busy_end)
        
        if current_time < end:
            free_slots.append((current_time, end))
        
        return free_slots
    
    def get_all_suggestions(
        self,
        look_ahead_hours: int = 24,
        now: Optional[datetime] = None,
    ) -> List[ScheduleSuggestion]:
        """Get all proactive suggestions."""
        
        now = now or datetime.now(timezone.utc)
        end_date = now + timedelta(hours=look_ahead_hours)
        
        # Fetch events
        events = self._fetch_calendar_events(now.isoformat(), end_date.isoformat())
        
        # Generate all suggestions
        all_suggestions = []
        
        all_suggestions.extend(self.generate_break_reminders(events, now))
        all_suggestions.extend(self.generate_meeting_prep_suggestions(events, now))
        all_suggestions.extend(self.generate_focus_block_suggestions(events, now))
        all_suggestions.extend(self.generate_alarm_adjustment_suggestions(events, now))
        all_suggestions.extend(self.generate_lighting_suggestions(events, now))
        all_suggestions.extend(self.generate_stress_relief_suggestions(events, now))
        
        lunch = self.generate_lunch_reminder(events, now)
        if lunch:
            all_suggestions.append(lunch)
        
        wrap = self.generate_end_of_day_suggestion(events, now)
        if wrap:
            all_suggestions.append(wrap)
        
        # Sort by priority
        priority_order = {
            SuggestionPriority.URGENT: 0,
            SuggestionPriority.HIGH: 1,
            SuggestionPriority.MEDIUM: 2,
            SuggestionPriority.LOW: 3,
        }
        
        all_suggestions.sort(key=lambda s: priority_order.get(s.priority, 4))
        
        # Store in history
        self._suggestion_history.extend(all_suggestions)
        
        return all_suggestions
    
    def dismiss_suggestion(self, suggestion: ScheduleSuggestion) -> None:
        """Mark a suggestion as dismissed."""
        suggestion_id = f"{suggestion.suggestion_type.value}:{suggestion.title}"
        self._dismissed_suggestions.append(suggestion_id)
    
    def accept_suggestion(self, suggestion: ScheduleSuggestion) -> Dict[str, Any]:
        """Process an accepted suggestion and return action details."""
        
        if suggestion.action_type == "schedule_break":
            return {
                "action": "create_event",
                "params": {
                    "summary": "Pause",
                    "duration_minutes": suggestion.action_params.get("duration_minutes", 10),
                    "type": "break",
                },
            }
        
        elif suggestion.action_type == "adjust_alarm":
            return {
                "action": "set_alarm",
                "params": {
                    "time": suggestion.action_params.get("suggested_time"),
                    "minutes_earlier": suggestion.action_params.get("minutes_earlier"),
                },
            }
        
        elif suggestion.action_type == "set_lighting_scene":
            return {
                "action": "activate_scene",
                "params": {
                    "scene": suggestion.action_params.get("scene"),
                },
            }
        
        elif suggestion.action_type == "schedule_focus":
            return {
                "action": "create_event",
                "params": {
                    "summary": "Fokus-Zeit",
                    "start": suggestion.action_params.get("start"),
                    "duration_minutes": suggestion.action_params.get("duration_minutes", 60),
                    "type": "focus",
                },
            }
        
        elif suggestion.action_type == "stress_relief":
            return {
                "action": "start_exercise",
                "params": {
                    "type": suggestion.action_params.get("type", "breathing"),
                    "duration_minutes": suggestion.action_params.get("duration_minutes", 5),
                },
            }
        
        return {"action": "none", "params": {}}
