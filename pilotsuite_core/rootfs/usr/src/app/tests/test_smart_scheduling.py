"""Tests for smart scheduling and mood-aware calendar features."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from copilot_core.calendar.smart_scheduler import (
    SmartScheduler,
    SmartSchedulerConfig,
    ScheduleRecommendation,
    EventType,
    EventPriority,
)
from copilot_core.calendar.mood_aware import (
    MoodAwareScheduler,
    MoodCalendarConfig,
)
from copilot_core.calendar.suggestions import (
    ScheduleSuggester,
    SuggestionConfig,
    SuggestionType,
    SuggestionPriority,
)
from copilot_core.mood.engine import MoodState, MoodResult, ZoneFeatures


class TestSmartScheduler:
    """Test smart scheduling engine."""
    
    @pytest.fixture
    def scheduler(self):
        """Create a smart scheduler instance."""
        config = SmartSchedulerConfig(
            work_start_hour=8,
            work_end_hour=18,
            break_duration_minutes=15,
            break_interval_minutes=90,
        )
        return SmartScheduler(config)
    
    def test_scheduler_initialization(self, scheduler):
        """Test scheduler creates with default config."""
        assert scheduler.config.work_start_hour == 8
        assert scheduler.config.work_end_hour == 18
        assert scheduler.config.break_duration_minutes == 15
    
    def test_recommend_slot_basic(self, scheduler):
        """Test basic slot recommendation."""
        with patch.object(scheduler, '_fetch_calendar_events', return_value=[]):
            recommendation = scheduler.recommend_slot(
                duration_minutes=30,
                event_type=EventType.TASK,
                priority=EventPriority.MEDIUM,
            )
            
            assert recommendation is not None
            assert recommendation.recommended_start is not None
            assert recommendation.recommended_end is not None
            assert 0.0 <= recommendation.confidence <= 1.0
            # reasons are internal
    
    def test_recommend_slot_with_conflicts(self, scheduler):
        """Test recommendation handles conflicts."""
        now = datetime.now(timezone.utc)
        
        # Create a conflicting event
        conflicting_event = {
            "summary": "Existing Meeting",
            "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
        }
        
        with patch.object(scheduler, '_fetch_calendar_events', return_value=[conflicting_event]):
            recommendation = scheduler.recommend_slot(
                duration_minutes=60,
                event_type=EventType.MEETING,
            )
            
            # Should find alternative slot or report conflict
            assert recommendation is not None
    
    def test_day_summary_empty(self, scheduler):
        """Test day summary with no events."""
        with patch.object(scheduler, '_fetch_calendar_events', return_value=[]):
            summary = scheduler.get_day_summary(datetime.now())
            
            assert summary["event_count"] == 0
            assert summary["meeting_count"] == 0
            assert summary["density"] == "light"
    
    def test_day_summary_busy(self, scheduler):
        """Test day summary with many meetings."""
        now = datetime.now(timezone.utc)
        
        events = [
            {
                "summary": f"Meeting {i}",
                "start": {"dateTime": (now.replace(hour=9+i, minute=0)).isoformat()},
                "end": {"dateTime": (now.replace(hour=10+i, minute=0)).isoformat()},
            }
            for i in range(6)
        ]
        
        with patch.object(scheduler, '_fetch_calendar_events', return_value=events):
            summary = scheduler.get_day_summary(now)
            
            assert summary["meeting_count"] >= 5
            assert summary["density"] in ("busy", "very_busy")
    
    def test_alarm_suggestion_early_meeting(self, scheduler):
        """Test alarm suggestion for early meeting."""
        tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0)
        
        events = [
            {
                "summary": "Early Meeting",
                "start": {"dateTime": tomorrow.isoformat()},
                "end": {"dateTime": (tomorrow + timedelta(hours=1)).isoformat()},
            }
        ]
        
        suggestion = scheduler.suggest_alarm_adjustment(events)
        
        if suggestion:
            assert "minutes_earlier" in suggestion
            assert "message" in suggestion
            assert "Früher Termin" in suggestion.get("reason", "")


class TestMoodAwareScheduler:
    """Test mood-aware scheduling."""
    
    @pytest.fixture
    def mood_scheduler(self):
        """Create mood-aware scheduler."""
        config = MoodCalendarConfig(
            avoid_meetings_during_stress=True,
            prefer_breaks_on_low_mood=True,
        )
        return MoodAwareScheduler(config)
    
    def test_set_current_mood(self, mood_scheduler):
        """Test setting current mood."""
        mood_result = MoodResult(
            mood=MoodState.FOCUS,
            confidence=0.8,
            reasons=["Active presence detected"],
            features=ZoneFeatures(
                stress_index=0.2,
                comfort_index=0.7,
                energy_level=0.8,
            ),
        )
        
        mood_scheduler.set_current_mood(mood_result)
        
        assert mood_scheduler._current_mood is not None
        assert mood_scheduler._current_mood.mood == MoodState.FOCUS
    
    def test_recommend_with_mood_stress(self, mood_scheduler):
        """Test recommendation adjusts for stress."""
        mood_result = MoodResult(
            mood=MoodState.STRESS,
            confidence=0.9,
            reasons=["High workload detected"],
            features=ZoneFeatures(
                stress_index=0.85,
                comfort_index=0.3,
                energy_level=0.4,
            ),
        )
        
        mood_scheduler.set_current_mood(mood_result)
        
        with patch.object(mood_scheduler.scheduler, '_fetch_calendar_events', return_value=[]):
            recommendation = mood_scheduler.recommend_with_mood(
                duration_minutes=30,
                event_type=EventType.MEETING,
                priority=EventPriority.MEDIUM,
            )
            
            # Should suggest break instead of meeting during high stress
            assert recommendation is not None
            assert any("stress" in r.lower() for r in recommendation.reasons)
    
    def test_recommend_with_mood_focus(self, mood_scheduler):
        """Test recommendation leverages focus mood."""
        mood_result = MoodResult(
            mood=MoodState.FOCUS,
            confidence=0.85,
            reasons=["Quiet environment, good lighting"],
            features=ZoneFeatures(
                stress_index=0.1,
                comfort_index=0.8,
                energy_level=0.85,
            ),
        )
        
        mood_scheduler.set_current_mood(mood_result)
        
        with patch.object(mood_scheduler.scheduler, '_fetch_calendar_events', return_value=[]):
            recommendation = mood_scheduler.recommend_with_mood(
                duration_minutes=90,
                event_type=EventType.TASK,
                priority=EventPriority.MEDIUM,
            )
            
            assert recommendation.confidence >= 0.5
            assert any("focus" in r.lower() for r in recommendation.reasons)
    
    def test_adjust_event_lighting(self, mood_scheduler):
        """Test lighting scene adjustment for events."""
        mood_result = MoodResult(
            mood=MoodState.FOCUS,
            confidence=0.8,
            reasons=[],
            features=ZoneFeatures(),
        )
        
        mood_scheduler.set_current_mood(mood_result)
        
        event = {
            "summary": "Team Meeting",
            "start": {"dateTime": (datetime.now() + timedelta(hours=1)).isoformat()},
            "end": {"dateTime": (datetime.now() + timedelta(hours=2)).isoformat()},
        }
        
        adjusted = mood_scheduler.adjust_event_for_mood(event)
        
        assert adjusted.mood_at_scheduling == "focus"
        assert adjusted.lighting_scene is not None


class TestScheduleSuggester:
    """Test proactive suggestion engine."""
    
    @pytest.fixture
    def suggester(self):
        """Create suggestion engine."""
        config = SuggestionConfig(
            break_reminder_interval_minutes=90,
            break_duration_minutes=10,
            stress_break_threshold=0.7,
        )
        return ScheduleSuggester(config)
    
    def test_break_reminder_generation(self, suggester):
        """Test break reminder suggestions."""
        now = datetime.now(timezone.utc)
        
        # Simulate last break 2 hours ago
        events = [
            {
                "summary": "Last Break",
                "start": {"dateTime": (now - timedelta(hours=2)).isoformat()},
                "end": {"dateTime": (now - timedelta(hours=2) + timedelta(minutes=15)).isoformat()},
            }
        ]
        
        with patch.object(suggester, '_fetch_calendar_events', return_value=[]):
            suggestions = suggester.generate_break_reminders(events, now)
            
            # Should suggest a break
            assert len(suggestions) > 0
            assert suggestions[0].suggestion_type == SuggestionType.BREAK_REMINDER
    
    def test_meeting_prep_suggestion(self, suggester):
        """Test meeting preparation suggestions."""
        now = datetime.now(timezone.utc)
        
        events = [
            {
                "summary": "Important Meeting",
                "start": {"dateTime": (now + timedelta(minutes=20)).isoformat()},
                "end": {"dateTime": (now + timedelta(hours=1, minutes=20)).isoformat()},
            }
        ]
        
        with patch.object(suggester, '_fetch_calendar_events', return_value=[]):
            suggestions = suggester.generate_meeting_prep_suggestions(events, now)
            
            assert len(suggestions) > 0
            assert suggestions[0].suggestion_type == SuggestionType.MEETING_PREP
    
    def test_alarm_adjustment_suggestion(self, suggester):
        """Test alarm adjustment for early meetings."""
        tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=7, minute=0)
        
        events = [
            {
                "summary": "Early Call",
                "start": {"dateTime": tomorrow.isoformat()},
                "end": {"dateTime": (tomorrow + timedelta(hours=1)).isoformat()},
            }
        ]
        
        with patch.object(suggester, '_fetch_calendar_events', return_value=events):
            suggestions = suggester.generate_alarm_adjustment_suggestions(events)
            
            if suggestions:
                assert suggestions[0].suggestion_type == SuggestionType.ALARM_ADJUSTMENT
                assert "minutes_earlier" in suggestions[0].action_params
    
    def test_stress_relief_suggestion(self, suggester):
        """Test stress relief suggestions."""
        # Mock high stress mood
        mock_mood = Mock()
        mock_mood.features.stress_index = 0.85
        mock_mood.mood = MoodState.STRESS
        
        with patch.object(suggester, '_get_current_mood', return_value=mock_mood):
            with patch.object(suggester, '_fetch_calendar_events', return_value=[]):
                suggestions = suggester.generate_stress_relief_suggestions([])
                
                assert len(suggestions) > 0
                assert suggestions[0].suggestion_type == SuggestionType.STRESS_RELIEF
                assert suggestions[0].priority == SuggestionPriority.HIGH
    
    def test_get_all_suggestions_priority_order(self, suggester):
        """Test suggestions are ordered by priority."""
        with patch.object(suggester, '_fetch_calendar_events', return_value=[]):
            with patch.object(suggester, '_get_current_mood', return_value=None):
                suggestions = suggester.get_all_suggestions(look_ahead_hours=24)
                
                # Should be sorted by priority
                priority_order = {
                    SuggestionPriority.URGENT: 0,
                    SuggestionPriority.HIGH: 1,
                    SuggestionPriority.MEDIUM: 2,
                    SuggestionPriority.LOW: 3,
                }
                
                for i in range(len(suggestions) - 1):
                    assert priority_order[suggestions[i].priority] <= priority_order[suggestions[i+1].priority]
    
    def test_accept_suggestion_action(self, suggester):
        """Test accepting a suggestion returns action."""
        from copilot_core.calendar.suggestions import ScheduleSuggestion
        
        suggestion = ScheduleSuggestion(
            suggestion_type=SuggestionType.BREAK_REMINDER,
            priority=SuggestionPriority.MEDIUM,
            title="Time for a break",
            message="You've been working for 90 minutes",
            action_type="schedule_break",
            action_params={"duration_minutes": 10},
        )
        
        action = suggester.accept_suggestion(suggestion)
        
        assert action["action"] == "create_event"
        assert "duration_minutes" in action["params"]


class TestScheduleRecommendation:
    """Test recommendation data structures."""
    
    def test_recommendation_to_dict(self):
        """Test recommendation serialization."""
        now = datetime.now(timezone.utc)
        
        rec = ScheduleRecommendation(
            recommended_start=now,
            recommended_end=now + timedelta(minutes=30),
            confidence=0.85,
            reasons=["Good energy level", "No conflicts"],
            alternative_slots=[(now + timedelta(hours=1), now + timedelta(hours=1, minutes=30))],
            conflicts=[],
            mood_impact="positive",
            energy_impact=0.15,
        )
        
        data = rec.to_dict()
        
        assert "recommended_start" in data
        assert "recommended_end" in data
        assert "confidence" in data
        assert "reasons" in data
        assert data["mood_impact"] == "positive"


class TestIntegration:
    """Integration tests for calendar module."""
    
    def test_full_scheduling_flow(self):
        """Test complete scheduling workflow."""
        # Initialize components
        config = SmartSchedulerConfig()
        scheduler = SmartScheduler(config)
        
        mood_config = MoodCalendarConfig()
        mood_scheduler = MoodAwareScheduler(mood_config, scheduler)
        
        suggestion_config = SuggestionConfig()
        suggester = ScheduleSuggester(suggestion_config, mood_scheduler)
        
        # Set mood state
        mood_result = MoodResult(
            mood=MoodState.NEUTRAL,
            confidence=0.5,
            reasons=[],
            features=ZoneFeatures(
                stress_index=0.3,
                comfort_index=0.6,
                energy_level=0.6,
            ),
        )
        mood_scheduler.set_current_mood(mood_result)
        
        # Get recommendations
        with patch.object(scheduler, '_fetch_calendar_events', return_value=[]):
            with patch.object(suggester, '_fetch_calendar_events', return_value=[]):
                # Get smart recommendation
                rec = scheduler.recommend_slot(
                    duration_minutes=60,
                    event_type=EventType.TASK,
                )
                assert rec is not None
                
                # Get mood-aware recommendation
                mood_rec = mood_scheduler.recommend_with_mood(
                    duration_minutes=60,
                    event_type=EventType.TASK,
                )
                assert mood_rec is not None
                
                # Get suggestions
                suggestions = suggester.get_all_suggestions()
                assert isinstance(suggestions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
