"""Symbiosis Integration Tests — Full Stack Validation.
Tests all components working together.
"""
import pytest
import asyncio
from copilot_core.symbiosis import (
    SymbioticRuleEngine,
    ContextManager,
    EventBusSync,
    PredictiveSymbiosisEngine,
    RuleOptimizer,
    LearningMemorySync,
)
import tempfile

class TestSymbiosisIntegration:
    """Integration tests for the full symbiosis stack."""

    def test_rule_engine_to_context_manager(self):
        """Test Rule Engine triggering Context transitions."""
        rule_engine = SymbioticRuleEngine()
        context_manager = ContextManager()
        
        # Register rule that changes context
        rule_id = rule_engine.register_rule(
            zone_id="zone.lr",
            rule_type="presence",
            condition={"logic": "AND", "checks": [{"type": "presence"}]},
            action={"type": "context_change", "context": "occupied"}
        )
        
        # Trigger evaluation
        actions = rule_engine.evaluate_zone(
            {"zone_id": "zone.lr"},
            [{"event_type": "presence"}]
        )
        
        # Execute action
        assert len(actions) == 1
        context_manager.transition("zone.lr", actions[0]["context"])
        
        # Verify
        assert context_manager.get_active_context("zone.lr") == "occupied"

    def test_predictive_to_rule_creation(self):
        """Test Predictive Engine generating rules."""
        predictive = PredictiveSymbiosisEngine()
        rule_engine = SymbioticRuleEngine()
        
        # Add pattern events
        for i in range(5):
            predictive.add_event({
                "event_type": "motion",
                "zone_id": "zone.lr",
                "timestamp": "2026-04-06T20:00:00Z"
            })
        
        # Analyze and get suggestions
        patterns = predictive.analyze_patterns()
        suggestions = predictive.get_suggested_rules()
        
        assert len(suggestions) >= 1
        
        # Create rule from suggestion
        suggestion = suggestions[0]
        rule_engine.register_rule(
            zone_id="zone.lr",
            rule_type="suggested",
            condition=suggestion["condition"],
            action=suggestion["action"]
        )
        
        assert len(rule_engine.rules) >= 1

    def test_optimizer_feedback_loop(self):
        """Test Rule Optimizer learning from feedback."""
        rule_engine = SymbioticRuleEngine()
        optimizer = RuleOptimizer(rule_engine)
        
        # Create and trigger rule
        rule_engine.register_rule("zone.lr", "test", {}, {})
        rule_engine.rules["rule_1"]["triggered_count"] = 10
        
        # Record executions
        for i in range(10):
            optimizer.record_execution("rule_1", {}, {})
        
        # Give negative feedback
        optimizer.record_feedback("rule_1", False)
        
        # Check score reflects feedback
        scores = optimizer.score_all_rules()
        assert scores[0].utility_score == 0.5  # Negative feedback

    def test_learning_memory_persistence(self):
        """Test Learning Memory persists across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LearningMemorySync(tmpdir)
            
            # Save patterns
            patterns = [
                {"pattern_id": "p1", "frequency": 5},
                {"pattern_id": "p2", "frequency": 10}
            ]
            memory.save_patterns(patterns)
            
            # New instance (simulates restart)
            memory2 = LearningMemorySync(tmpdir)
            loaded = memory2.load_patterns()
            
            assert len(loaded) == 2
            assert loaded[0]["pattern_id"] == "p1"

    def test_full_event_chain(self):
        """Test complete event → rule → action chain."""
        rule_engine = SymbioticRuleEngine()
        context_manager = ContextManager()
        predictive = PredictiveSymbiosisEngine()
        
        # 1. Add events for pattern detection
        for i in range(5):
            predictive.add_event({
                "event_type": "presence",
                "zone_id": "zone.lr",
                "timestamp": "2026-04-06T20:00:00Z"
            })
        
        # 2. Detect patterns
        predictive.analyze_patterns()
        suggestions = predictive.get_suggested_rules()
        
        # 3. Create rule from suggestion
        if suggestions:
            rule_engine.register_rule(
                zone_id="zone.lr",
                rule_type="auto_generated",
                condition=suggestions[0]["condition"],
                action=suggestions[0]["action"]
            )
        
        # 4. Trigger rule with new event
        actions = rule_engine.evaluate_zone(
            {"zone_id": "zone.lr"},
            [{"event_type": "presence"}]
        )
        
        # 5. Execute action
        if actions:
            action = actions[0]
            if action.get("type") == "context_change":
                context_manager.transition("zone.lr", action["context"])
        
        # Verify chain completed
        assert context_manager.get_active_context("zone.lr") in ["occupied", "ready"]


class TestPerformanceBenchmarks:
    """Basic performance benchmarks."""

    def test_rule_evaluation_speed(self):
        """Test rule evaluation is under 10ms."""
        import time
        
        rule_engine = SymbioticRuleEngine()
        
        # Create 100 rules
        for i in range(100):
            rule_engine.register_rule(
                f"zone_{i}",
                "test",
                {"logic": "AND", "checks": [{"type": "test"}]},
                {}
            )
        
        # Measure evaluation time
        start = time.time()
        for i in range(100):
            rule_engine.evaluate_zone(
                {"zone_id": f"zone_{i}"},
                [{"event_type": "test"}]
            )
        elapsed = time.time() - start
        
        # Should be under 100ms for 100 evaluations (1ms avg)
        assert elapsed < 0.1, f"Evaluation too slow: {elapsed*1000}ms"

    def test_pattern_detection_speed(self):
        """Test pattern detection is under 50ms."""
        import time
        
        predictive = PredictiveSymbiosisEngine()
        
        # Add 100 events
        for i in range(100):
            predictive.add_event({
                "event_type": "motion",
                "zone_id": "zone.lr",
                "timestamp": "2026-04-06T20:00:00Z"
            })
        
        # Measure analysis time
        start = time.time()
        predictive.analyze_patterns()
        elapsed = time.time() - start
        
        # Should be under 50ms
        assert elapsed < 0.05, f"Analysis too slow: {elapsed*1000}ms"
