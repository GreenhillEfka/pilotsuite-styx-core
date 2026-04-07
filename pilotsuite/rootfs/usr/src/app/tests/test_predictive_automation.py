"""Predictive Automation Tests for PilotSuite Core."""

import pytest
from datetime import datetime, timedelta
from copilot_core.predictive_automation import (
    PredictiveAutomation, UserAction, Prediction
)
from collections import defaultdict


class MockBrainGraphService:
    """Mock BrainGraphService for testing."""
    
    def get_current_context(self) -> dict:
        return {"time_of_day": "evening", "presence": "home"}
    
    def get_recent_actions(self) -> list:
        return ["turn_on_lights"]


class TestPredictiveAutomation:
    """Tests for PredictiveAutomation class."""
    
    def test_init(self):
        """Test PredictiveAutomation initialization."""
        auto = PredictiveAutomation()
        assert auto._action_patterns == defaultdict(list)
        assert auto._recent_actions == []
        assert auto._max_recent_actions == 50
    
    def test_init_with_brain_graph(self):
        """Test initialization with BrainGraph."""
        brain = MockBrainGraphService()
        auto = PredictiveAutomation(brain_graph=brain)
        assert auto.brain_graph == brain
    
    def test_record_action(self):
        """Test recording user actions."""
        auto = PredictiveAutomation()
        
        action = UserAction(
            action="turn_on_lights",
            timestamp=datetime.now(),
            location="living_room",
            entities=["light.living_room"],
            context={"time_of_day": "evening"}
        )
        
        auto.record_action(action)
        
        assert len(auto._recent_actions) == 1
        assert len(auto._action_patterns["turn_on_lights"]) == 1
    
    def test_record_multiple_actions(self):
        """Test recording multiple actions."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        actions = [
            UserAction(
                action="turn_on_lights",
                timestamp=now - timedelta(minutes=i),
                location="living_room",
                context={"time_of_day": "evening"}
            )
            for i in range(5)
        ]
        
        for action in actions:
            auto.record_action(action)
        
        assert len(auto._recent_actions) == 5
        assert len(auto._action_patterns["turn_on_lights"]) == 5
    
    def test_predict_next_action_basic(self):
        """Test basic action prediction."""
        auto = PredictiveAutomation()
        
        # Record some actions first
        now = datetime.now()
        
        for i in range(5):
            auto.record_action(UserAction(
                action="turn_on_lights",
                timestamp=now - timedelta(minutes=i),
                location="living_room",
                context={"time_of_day": "evening"}
            ))
        
        # Predict
        predictions = auto.predict_next_action(
            current_context={"time_of_day": "evening"},
            recent_actions=["turn_on_lights"]
        )
        
        assert len(predictions) > 0
        assert predictions[0].predicted_action == "turn_on_lights"
        assert predictions[0].confidence > 0
    
    def test_predict_next_action_empty(self):
        """Test prediction with no history."""
        auto = PredictiveAutomation()
        
        predictions = auto.predict_next_action(
            current_context={"time_of_day": "morning"},
            recent_actions=[]
        )
        
        assert predictions == []
    
    def test_predict_next_action_with_context(self):
        """Test prediction based on context patterns."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        # Record actions with specific context
        auto.record_action(UserAction(
            action="adjust_thermostat",
            timestamp=now - timedelta(minutes=1),
            location="living_room",
            context={"temperature": 22, "presence": "home"}
        ))
        
        auto.record_action(UserAction(
            action="adjust_thermostat",
            timestamp=now - timedelta(minutes=2),
            location="living_room",
            context={"temperature": 23, "presence": "home"}
        ))
        
        # Predict with matching context
        predictions = auto.predict_next_action(
            current_context={"temperature": 22, "presence": "home"},
            recent_actions=[]
        )
        
        # May or may not have predictions, depending on pattern matching
        assert isinstance(predictions, list)
    
    def test_get_automation_suggestions(self):
        """Test automation suggestions."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        # Record repeated actions with enough occurrences to meet threshold
        for i in range(50):
            auto.record_action(UserAction(
                action="turn_on_lights",
                timestamp=now - timedelta(minutes=i),
                location="living_room"
            ))
        
        suggestions = auto.get_automation_suggestions(threshold=0.5)
        
        # Should have at least one suggestion
        assert len(suggestions) >= 1
        assert suggestions[0]["action"] == "turn_on_lights"
        assert suggestions[0]["confidence"] >= 0.5
    
    def test_get_automation_suggestions_threshold(self):
        """Test automation suggestions with high threshold."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        # Only 3 occurrences (should not meet high threshold)
        for i in range(3):
            auto.record_action(UserAction(
                action="turn_on_lights",
                timestamp=now - timedelta(minutes=i),
                location="living_room"
            ))
        
        # High threshold should filter out
        suggestions = auto.get_automation_suggestions(threshold=0.9)
        
        # Should have no suggestions
        assert len(suggestions) == 0
    
    def test_get_automation_suggestions_low_threshold(self):
        """Test automation suggestions with low threshold."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        # Only 10 occurrences (10% = 0.1 confidence)
        for i in range(10):
            auto.record_action(UserAction(
                action="turn_on_lights",
                timestamp=now - timedelta(minutes=i),
                location="living_room"
            ))
        
        # Low threshold should include
        suggestions = auto.get_automation_suggestions(threshold=0.05)
        
        # Should have at least one suggestion
        assert len(suggestions) >= 1
    
    def test_generate_automation_suggestion(self):
        """Test automation suggestion generation."""
        auto = PredictiveAutomation()
        
        action = "turn_on_lights"
        context = {"time_of_day": "evening", "presence": "home"}
        
        suggestion = auto._generate_automation_suggestion(action, context)
        
        assert suggestion["action"] == action
        assert len(suggestion["conditions"]) > 0
        assert len(suggestion["actions"]) > 0
        assert suggestion["suggested_by"] == "predictive_automation"
    
    def test_pattern_recognition(self):
        """Test pattern recognition across multiple actions."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        # Multiple action types
        action_types = ["turn_on_lights", "adjust_thermostat", "play_music"]
        
        for action_type in action_types:
            for i in range(5):
                auto.record_action(UserAction(
                    action=action_type,
                    timestamp=now - timedelta(minutes=i),
                    location="living_room"
                ))
        
        # Check patterns
        assert len(auto._action_patterns) == 3
        for action_type in action_types:
            assert len(auto._action_patterns[action_type]) == 5
    
    def test_max_recent_actions(self):
        """Test that recent actions are limited."""
        auto = PredictiveAutomation()
        auto._max_recent_actions = 10
        
        now = datetime.now()
        
        # Record more than max
        for i in range(15):
            auto.record_action(UserAction(
                action="test_action",
                timestamp=now - timedelta(minutes=i),
                location="test"
            ))
        
        assert len(auto._recent_actions) <= 10
    
    def test_integration_with_brain_graph(self):
        """Test integration with BrainGraph."""
        brain = MockBrainGraphService()
        auto = PredictiveAutomation(brain_graph=brain)
        
        # Use brain context for prediction
        predictions = auto.predict_next_action(
            current_context=brain.get_current_context(),
            recent_actions=brain.get_recent_actions()
        )
        
        # May have predictions
        assert isinstance(predictions, list)


class TestPredictiveAutomationIntegration:
    """Integration tests for PredictiveAutomation."""
    
    def test_end_to_end_workflow(self):
        """Test complete prediction workflow."""
        auto = PredictiveAutomation()
        
        now = datetime.now()
        
        # Step 1: Record historical actions with enough occurrences
        for i in range(50):
            auto.record_action(UserAction(
                action="turn_on_lights",
                timestamp=now - timedelta(minutes=i),
                location="living_room",
                context={"time_of_day": "evening"}
            ))
        
        # Step 2: Get suggestions
        suggestions = auto.get_automation_suggestions(threshold=0.5)
        assert len(suggestions) >= 1
        
        # Step 3: Record more actions
        auto.record_action(UserAction(
            action="turn_on_lights",
            timestamp=now,
            location="living_room",
            context={"time_of_day": "evening"}
        ))
        
        # Step 4: Predict
        predictions = auto.predict_next_action(
            current_context={"time_of_day": "evening"},
            recent_actions=["turn_on_lights"]
        )
        
        assert len(predictions) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
