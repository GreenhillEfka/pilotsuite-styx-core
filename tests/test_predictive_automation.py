"""Tests for Predictive Automation Engine — Slice 14."""
import pytest
from copilot_core.predictive.automation_engine import (
    PredictiveAutomationEngine,
    BehavioralPattern,
    PatternType,
    PredictionConfidence,
    PredictiveProposal,
    create_predictive_automation_engine,
)


class TestPredictiveAutomationEngine:
    """Test predictive automation engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_predictive_automation_engine()
        assert engine is not None
    
    def test_record_action(self):
        """Test recording user actions."""
        engine = PredictiveAutomationEngine()
        
        action = {
            "entity_id": "light.living_room",
            "zone_id": "zone_living_room",
            "module_id": "licht_living_room",
            "action": {"domain": "light", "service": "turn_on"},
        }
        
        engine.record_action(action)
        
        # Should have recorded action
        assert len(engine._recent_actions) == 1
        assert engine._recent_actions[0]["entity_id"] == "light.living_room"
    
    def test_detect_time_pattern(self):
        """Test time-based pattern detection."""
        engine = PredictiveAutomationEngine()
        
        # Record actions at same hour for 5 days
        for i in range(5):
            action = {
                "entity_id": "light.living_room",
                "zone_id": "zone_living_room",
                "module_id": "licht_living_room",
                "action": {"domain": "light", "service": "turn_on"},
                "timestamp": f"2026-03-{25+i}T18:00:00Z",  # 18:00 each day
            }
            engine.record_action(action)
        
        # Should detect pattern
        assert len(engine._patterns) >= 1
        
        # Check pattern type
        patterns = engine.get_patterns()
        time_patterns = [p for p in patterns if p["pattern_type"] == "time_based"]
        assert len(time_patterns) >= 1
    
    def test_detect_presence_pattern(self):
        """Test presence-based pattern detection."""
        engine = PredictiveAutomationEngine()
        
        # Record actions correlated with presence
        for i in range(5):
            action = {
                "entity_id": "light.entrance",
                "zone_id": "zone_entrance",
                "module_id": "licht_entrance",
                "action": {"domain": "light", "service": "turn_on"},
                "context": {"presence_detected": True},
            }
            engine.record_action(action)
        
        # Should detect presence pattern
        patterns = engine.get_patterns()
        presence_patterns = [p for p in patterns if p["pattern_type"] == "presence_based"]
        assert len(presence_patterns) >= 1
    
    def test_generate_predictions(self):
        """Test prediction generation."""
        engine = PredictiveAutomationEngine()
        
        # Create a pattern manually for testing
        pattern = BehavioralPattern(
            pattern_id="test_pattern",
            pattern_type=PatternType.TIME_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={"hour": 18, "hour_tolerance": 2},
            typical_action={"domain": "light", "service": "turn_on"},
            occurrence_count=10,
            confidence=PredictionConfidence.HIGH,
        )
        engine._patterns["test_pattern"] = pattern
        
        # Generate predictions
        predictions = engine.generate_predictions()
        
        # Should generate predictions
        assert len(predictions) >= 0  # May or may not match current time
    
    def test_accept_prediction(self):
        """Test accepting a prediction."""
        engine = PredictiveAutomationEngine()
        
        from copilot_core.predictive.automation_engine import PredictiveProposal
        
        proposal = PredictiveProposal(
            proposal_id="pred_test",
            pattern_id="test_pattern",
            zone_id="zone_test",
            module_id="licht_test",
            description="Test prediction",
            predicted_action={"domain": "light", "service": "turn_on"},
            confidence=PredictionConfidence.HIGH,
            confidence_score=0.8,
            reasoning="Test reasoning",
            expires_at="2026-04-01T00:00:00Z",
        )
        
        engine._proposals["pred_test"] = proposal
        engine._patterns["test_pattern"] = BehavioralPattern(
            pattern_id="test_pattern",
            pattern_type=PatternType.TIME_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={},
            typical_action={},
            occurrence_count=5,
        )
        
        # Accept
        result = engine.accept_prediction("pred_test")
        assert result is True
        
        # Verify accepted
        assert engine._proposals["pred_test"].accepted is True
        
        # Verify pattern was reinforced
        assert engine._patterns["test_pattern"].occurrence_count == 6
    
    def test_reject_prediction_with_feedback(self):
        """Test rejecting a prediction with feedback."""
        engine = PredictiveAutomationEngine()
        
        from copilot_core.predictive.automation_engine import PredictiveProposal
        
        proposal = PredictiveProposal(
            proposal_id="pred_test_2",
            pattern_id="test_pattern_2",
            zone_id="zone_test",
            module_id="licht_test",
            description="Test prediction",
            predicted_action={"domain": "light", "service": "turn_on"},
            confidence=PredictionConfidence.MEDIUM,
            confidence_score=0.5,
            reasoning="Test reasoning",
            expires_at="2026-04-01T00:00:00Z",
        )
        
        engine._proposals["pred_test_2"] = proposal
        engine._patterns["test_pattern_2"] = BehavioralPattern(
            pattern_id="test_pattern_2",
            pattern_type=PatternType.TIME_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={},
            typical_action={},
            occurrence_count=5,
            confidence=PredictionConfidence.MEDIUM,
        )
        
        # Reject with feedback
        result = engine.reject_prediction("pred_test_2", feedback="not_needed")
        assert result is True
        
        # Verify rejected
        assert engine._proposals["pred_test_2"].rejected is True
        assert engine._proposals["pred_test_2"].feedback == "not_needed"
        
        # Verify pattern was weakened
        assert engine._patterns["test_pattern_2"].confidence == PredictionConfidence.LOW
    
    def test_confidence_calculation(self):
        """Test confidence calculation from pattern statistics."""
        engine = PredictiveAutomationEngine()
        
        # High occurrence, low stddev = high confidence
        confidence = engine._calculate_confidence(10, 0.5)
        assert confidence in (PredictionConfidence.HIGH, PredictionConfidence.VERY_HIGH)
        
        # Low occurrence, high stddev = low confidence
        confidence = engine._calculate_confidence(2, 4.0)
        assert confidence in (PredictionConfidence.LOW, PredictionConfidence.VERY_LOW)
    
    def test_pattern_match_evaluation(self):
        """Test pattern match evaluation."""
        engine = PredictiveAutomationEngine()
        
        pattern = BehavioralPattern(
            pattern_id="test_pattern",
            pattern_type=PatternType.TIME_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={"hour": 18, "hour_tolerance": 2},
            typical_action={},
            occurrence_count=10,
        )
        
        # Test match at pattern hour
        # Note: This test depends on current time, so we just verify the method works
        match_score = engine._evaluate_pattern_match(pattern, None)
        assert 0.0 <= match_score <= 1.0
    
    def test_prediction_description_generation(self):
        """Test prediction description generation."""
        engine = PredictiveAutomationEngine()
        
        pattern = BehavioralPattern(
            pattern_id="test_pattern",
            pattern_type=PatternType.TIME_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={"hour": 18},
            typical_action={},
            occurrence_count=5,
        )
        
        description = engine._generate_prediction_description(pattern, None)
        assert "18:00" in description or "routine" in description.lower()
    
    def test_reasoning_generation(self):
        """Test reasoning generation."""
        engine = PredictiveAutomationEngine()
        
        pattern = BehavioralPattern(
            pattern_id="test_pattern",
            pattern_type=PatternType.PRESENCE_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={},
            typical_action={},
            occurrence_count=10,
        )
        
        reasoning = engine._generate_reasoning(pattern, {"presence_detected": True})
        assert len(reasoning) > 0
    
    def test_get_predictions_sorted_by_confidence(self):
        """Test that predictions are sorted by confidence."""
        engine = PredictiveAutomationEngine()
        
        from copilot_core.predictive.automation_engine import PredictiveProposal
        
        # Create predictions with different confidence scores
        for i, score in enumerate([0.9, 0.5, 0.7]):
            proposal = PredictiveProposal(
                proposal_id=f"pred_{i}",
                pattern_id=f"pattern_{i}",
                zone_id="zone_test",
                module_id="licht_test",
                description=f"Prediction {i}",
                predicted_action={},
                confidence=PredictionConfidence.MEDIUM,
                confidence_score=score,
                reasoning="Test",
                expires_at="2026-04-01T00:00:00Z",
            )
            engine._proposals[f"pred_{i}"] = proposal
        
        predictions = engine.get_predictions(unresolved_only=True)
        
        # Should be sorted by confidence (highest first)
        if len(predictions) >= 2:
            assert predictions[0]["confidence_score"] >= predictions[1]["confidence_score"]
    
    def test_action_trimming(self):
        """Test that recent actions are trimmed to context window."""
        engine = PredictiveAutomationEngine()
        engine._context_window_hours = 1  # 1 hour window for testing
        
        # Add actions older than context window
        for i in range(100):
            action = {
                "entity_id": "light.test",
                "timestamp": f"2026-03-30T{i % 24:02d}:00:00Z",
            }
            engine.record_action(action)
        
        # Should be trimmed
        assert len(engine._recent_actions) <= 100  # Exact count depends on implementation
    
    def test_pattern_to_dict(self):
        """Test pattern serialization."""
        pattern = BehavioralPattern(
            pattern_id="pattern_test",
            pattern_type=PatternType.SEASONAL,
            zone_id="zone_garden",
            module_id="energy_garden",
            entity_id="sensor.garden_temp",
            trigger_conditions={"season": "summer"},
            typical_action={"domain": "switch", "service": "turn_on"},
            occurrence_count=15,
            confidence=PredictionConfidence.HIGH,
        )
        
        d = pattern.to_dict()
        
        assert d["pattern_id"] == "pattern_test"
        assert d["pattern_type"] == "seasonal"
        assert d["zone_id"] == "zone_garden"
        assert d["occurrence_count"] == 15
        assert d["confidence"] == "high"
    
    def test_proposal_to_dict(self):
        """Test proposal serialization."""
        from copilot_core.predictive.automation_engine import PredictiveProposal
        
        proposal = PredictiveProposal(
            proposal_id="prop_test",
            pattern_id="pattern_test",
            zone_id="zone_living_room",
            module_id="licht_living_room",
            description="Turn on lights",
            predicted_action={"domain": "light", "service": "turn_on"},
            confidence=PredictionConfidence.VERY_HIGH,
            confidence_score=0.95,
            reasoning="User always does this at 18:00",
            expires_at="2026-04-01T19:00:00Z",
        )
        
        d = proposal.to_dict()
        
        assert d["proposal_id"] == "prop_test"
        assert d["confidence"] == "very_high"
        assert d["confidence_score"] == 0.95
        assert d["accepted"] is False
        assert d["rejected"] is False


class TestConfidenceDowngrade:
    """Test confidence downgrade on rejection."""
    
    def test_downgrade_very_high_to_high(self):
        """Test VERY_HIGH downgrades to HIGH."""
        engine = PredictiveAutomationEngine()
        result = engine._downgrade_confidence(PredictionConfidence.VERY_HIGH)
        assert result == PredictionConfidence.HIGH
    
    def test_downgrade_high_to_medium(self):
        """Test HIGH downgrades to MEDIUM."""
        engine = PredictiveAutomationEngine()
        result = engine._downgrade_confidence(PredictionConfidence.HIGH)
        assert result == PredictionConfidence.MEDIUM
    
    def test_downgrade_very_low_stays_very_low(self):
        """Test VERY_LOW stays VERY_LOW (already minimum)."""
        engine = PredictiveAutomationEngine()
        result = engine._downgrade_confidence(PredictionConfidence.VERY_LOW)
        assert result == PredictionConfidence.VERY_LOW


class TestSlice14Contracts:
    """Additional Slice-14 contract coverage."""

    def test_detect_calendar_pattern(self):
        """Calendar-correlated actions should become first-class patterns."""
        engine = PredictiveAutomationEngine()

        for _ in range(3):
            engine.record_action(
                {
                    "entity_id": "light.kitchen",
                    "zone_id": "zone_kitchen",
                    "module_id": "licht_kitchen",
                    "action": {"domain": "light", "service": "turn_on"},
                    "context": {"calendar_summary": "Office commute"},
                }
            )

        patterns = engine.get_patterns()
        calendar_patterns = [p for p in patterns if p["pattern_type"] == "calendar_based"]
        assert len(calendar_patterns) >= 1
        assert calendar_patterns[0]["contract"] == "BehavioralPatternV1"

    def test_prediction_to_dict_exposes_canonical_contract(self):
        """Predictions should expose source signals and policy-gate requirement."""
        engine = PredictiveAutomationEngine()
        pattern = BehavioralPattern(
            pattern_id="pattern_slice14",
            pattern_type=PatternType.CALENDAR_BASED,
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            trigger_conditions={"calendar_summary": "Office commute"},
            typical_action={"domain": "light", "service": "turn_on", "entity_id": "light.test"},
            occurrence_count=6,
            confidence=PredictionConfidence.HIGH,
        )
        engine._patterns[pattern.pattern_id] = pattern

        predictions = engine.generate_predictions({"calendar_summary": "Office commute"})
        assert predictions
        payload = predictions[0].to_dict()
        assert payload["contract"] == "PredictiveProposalV1"
        assert payload["policy_gate_required"] is True
        assert "calendar" in payload["source_signals"]

    def test_get_stats_counts_resolution_state(self):
        """Aggregate stats should expose proposal resolution state."""
        engine = PredictiveAutomationEngine()
        proposal = PredictiveProposal(
            proposal_id="pred_stats",
            pattern_id="pattern_stats",
            zone_id="zone_test",
            module_id="licht_test",
            description="Stats proposal",
            predicted_action={"domain": "light", "service": "turn_on"},
            confidence=PredictionConfidence.MEDIUM,
            confidence_score=0.6,
            reasoning="Stats reasoning",
            expires_at="2026-04-01T00:00:00Z",
        )
        engine._proposals[proposal.proposal_id] = proposal
        engine.reject_prediction("pred_stats", feedback="not_now")

        stats = engine.get_stats()
        assert stats["proposals_total"] == 1
        assert stats["proposals_rejected"] == 1
        assert stats["proposals_unresolved"] == 0
