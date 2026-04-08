# Smart Scheduling & Mood-Aware Calendar

Intelligent calendar management with mood awareness, energy optimization, and proactive suggestions.

## Overview

This module extends the basic HA calendar integration with:

- **Smart Scheduling Engine** (`smart_scheduler.py`) — Intelligent time slot recommendations based on working hours, energy levels, and existing commitments
- **Mood-Aware Scheduler** (`mood_aware.py`) — Context-aware scheduling that adapts to current mood state and stress levels
- **Proactive Suggestions** (`suggestions.py`) — Automated recommendations for breaks, focus time, alarm adjustments, and lighting scenes

## Features

### Smart Scheduling

- Working hours configuration (default: 8-18)
- Automatic break scheduling (every 90 minutes)
- Lunch break detection and recommendation
- Meeting buffer times (5 minutes between meetings)
- Focus block optimization (morning peak hours: 9-12)
- Conflict detection and alternative slot suggestions

### Mood Integration

- Stress-aware scheduling (avoids meetings during high stress)
- Energy-based recommendations (focus tasks during high energy)
- Automatic lighting scene adjustments for events
- Break suggestions based on mood state
- Calendar density analysis with mood context

### Proactive Suggestions

Generated suggestions include:

| Type | Priority | Trigger |
|------|----------|---------|
| `break_reminder` | Medium/High | 90+ minutes without break |
| `meeting_prep` | Medium | 15 minutes before meeting |
| `focus_block` | Medium | Free slot during peak energy |
| `alarm_adjustment` | High | Early meeting tomorrow |
| `lighting_scene` | Low | Event with mood context |
| `stress_relief` | High | Stress index > 0.7 |
| `lunch_reminder` | Medium | No lunch scheduled by 12:30 |
| `end_of_day_wrap` | Medium | 30 minutes before end of day |

## API Endpoints

### Basic Calendar

```
GET  /api/v1/calendar                    # List calendar entities
GET  /api/v1/calendar/events/today       # Today's events
GET  /api/v1/calendar/events/upcoming    # Upcoming events (7 days default)
```

### Smart Scheduling

```
POST /api/v1/calendar/smart/recommend        # Get time slot recommendation
GET  /api/v1/calendar/smart/day-summary      # Day summary with density
GET  /api/v1/calendar/smart/alarm-suggestion # Alarm adjustment suggestion
```

### Mood-Aware

```
POST /api/v1/calendar/mood/recommend         # Mood-aware recommendation
GET  /api/v1/calendar/mood/summary           # Calendar summary with mood insights
POST /api/v1/calendar/mood/adjust-event      # Adjust event for current mood
POST /api/v1/calendar/mood/lighting-automation # Create lighting automation
```

### Suggestions

```
GET  /api/v1/calendar/suggestions            # Get all proactive suggestions
POST /api/v1/calendar/suggestions/:id/accept # Accept suggestion
POST /api/v1/calendar/suggestions/:id/dismiss # Dismiss suggestion
```

## Usage Examples

### Smart Slot Recommendation

```python
from copilot_core.calendar.smart_scheduler import SmartScheduler, EventType, EventPriority

scheduler = SmartScheduler()
recommendation = scheduler.recommend_slot(
    duration_minutes=60,
    event_type=EventType.TASK,
    priority=EventPriority.MEDIUM,
    look_ahead_days=3,
)

print(f"Best slot: {recommendation.recommended_start}")
print(f"Confidence: {recommendation.confidence}")
print(f"Reasons: {recommendation.reasons}")
```

### Mood-Aware Scheduling

```python
from copilot_core.calendar.mood_aware import MoodAwareScheduler, MoodCalendarConfig
from copilot_core.mood.engine import MoodState, MoodResult, ZoneFeatures

# Initialize
config = MoodCalendarConfig(
    avoid_meetings_during_stress=True,
    stress_threshold=0.7,
)
scheduler = MoodAwareScheduler(config)

# Set current mood
mood_result = MoodResult(
    mood=MoodState.FOCUS,
    confidence=0.85,
    reasons=["Quiet environment"],
    features=ZoneFeatures(
        stress_index=0.2,
        energy_level=0.8,
    ),
)
scheduler.set_current_mood(mood_result)

# Get recommendation
rec = scheduler.recommend_with_mood(
    duration_minutes=90,
    event_type=EventType.TASK,
)
```

### Proactive Suggestions

```python
from copilot_core.calendar.suggestions import ScheduleSuggester, SuggestionConfig

config = SuggestionConfig(
    break_reminder_interval_minutes=90,
    stress_break_threshold=0.7,
)
suggester = ScheduleSuggester(config)

# Get all suggestions
suggestions = suggester.get_all_suggestions(look_ahead_hours=24)

for s in suggestions:
    print(f"[{s.priority.value}] {s.title}: {s.message}")
    
    # Accept suggestion
    if s.title == "Zeit für eine Pause":
        action = suggester.accept_suggestion(s)
        # action['action'] == 'create_event'
```

### LLM Context Integration

```python
from copilot_core.api.v1.calendar import get_calendar_context_for_llm

context = get_calendar_context_for_llm()
# Returns formatted string with today's events, mood insights, and alarm suggestions
```

## Configuration

### SmartSchedulerConfig

```python
@dataclass
class SmartSchedulerConfig:
    work_start_hour: int = 8
    work_end_hour: int = 18
    break_duration_minutes: int = 15
    break_interval_minutes: int = 90
    lunch_start_hour: int = 12
    lunch_end_hour: int = 14
    lunch_duration_minutes: int = 60
    meeting_buffer_minutes: int = 5
    focus_block_min_minutes: int = 60
    respect_mood_states: bool = True
    avoid_focus_during_stress: bool = True
    prefer_breaks_on_low_energy: bool = True
    energy_aware: bool = True
    peak_energy_hours: Tuple[int, int] = (9, 12)
    max_meetings_per_day: int = 6
    max_consecutive_meetings: int = 3
```

### MoodCalendarConfig

```python
@dataclass
class MoodCalendarConfig:
    avoid_meetings_during_stress: bool = True
    prefer_breaks_on_low_mood: bool = True
    schedule_focus_when_calm: bool = True
    stress_threshold: float = 0.7
    low_energy_threshold: float = 0.3
    high_energy_threshold: float = 0.7
    auto_reschedule_low_priority: bool = False
    suggest_breaks_after_meetings: bool = True
    break_duration_minutes: int = 10
    adjust_lighting_for_meetings: bool = True
    adjust_lighting_for_focus: bool = True
    mood_sensor_entity: Optional[str] = "sensor.mood_state"
```

## Lighting Scenes

The module supports automatic lighting scene selection based on event type and mood:

| Scene | Trigger | Brightness | Color Temp |
|-------|---------|------------|------------|
| `meeting_focus` | Meeting + Focus mood | 80% | 400K (cool) |
| `meeting_calm` | Meeting + Stress mood | 60% | 350K (neutral) |
| `meeting_default` | Meeting | 70% | 370K |
| `relax_warm` | Lunch/Break | 50% | 250K (warm) |
| `focus_cool` | Focus task | 85% | 450K (very cool) |

## Testing

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
pytest -q tests/test_smart_scheduling.py
```

## Integration with PilotSuite

The calendar module integrates with:

- **Mood Engine** — Reads current mood state from `sensor.mood_state`
- **Habitus** — Learns scheduling patterns over time
- **Home Assistant** — Uses HA calendars and lighting control
- **LLM Context** — Provides calendar context for conversations

## Future Enhancements

- [ ] Bi-directional HA calendar sync
- [ ] Recurring event pattern learning
- [ ] Multi-user calendar coordination
- [ ] Travel time consideration
- [ ] Timezone-aware scheduling
- [ ] Natural language event creation
