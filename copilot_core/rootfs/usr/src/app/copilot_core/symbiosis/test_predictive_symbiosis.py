"""Predictive Symbiosis Tests — Pattern Detection + Rule Optimization."""
import pytest
from copilot_core.symbiosis.predictive_symbiosis import PredictiveSymbiosisEngine, PatternCandidate
from copilot_core.symbiosis.rule_optimizer import RuleOptimizer, RuleScore
from copilot_core.symbiosis.learning_memory_sync import LearningMemorySync
import tempfile
import os

class TestPredictiveSymbiosisEngine:
    def test_add_event(self):
        engine = PredictiveSymbiosisEngine()
        engine.add_event({"event_type": "motion", "zone_id": "zone.lr"})
        assert len(engine.event_history) == 1
    
    def test_event_history_limit(self):
        engine = PredictiveSymbiosisEngine()
        for i in range(1100):
            engine.add_event({"event_type": "motion", "zone_id": "zone.lr"})
        assert len(engine.event_history) == 1000
    
    def test_analyze_patterns_finds_frequent(self):
        engine = PredictiveSymbiosisEngine()
        # Add 5 events at same hour/zone
        for i in range(5):
            engine.add_event({
                "event_type": "presence",
                "zone_id": "zone.lr",
                "timestamp": "2026-04-06T20:00:00Z"
            })
        
        patterns = engine.analyze_patterns()
        assert len(patterns) >= 1
        assert patterns[0].frequency == 5
    
    def test_infer_action_presence(self):
        engine = PredictiveSymbiosisEngine()
        events = [{"event_type": "presence"} for _ in range(5)]
        action = engine._infer_action(events)
        assert action["type"] == "context_change"
        assert action["context"] == "occupied"
    
    def test_infer_action_motion(self):
        engine = PredictiveSymbiosisEngine()
        events = [{"event_type": "motion"} for _ in range(5)]
        action = engine._infer_action(events)
        assert action["type"] == "ha_service"
        assert action["service"] == "light.turn_on"
    
    def test_get_suggested_rules(self):
        engine = PredictiveSymbiosisEngine()
        for i in range(5):
            engine.add_event({
                "event_type": "motion",
                "zone_id": "zone.lr",
                "timestamp": "2026-04-06T20:00:00Z"
            })
        engine.analyze_patterns()
        rules = engine.get_suggested_rules()
        assert len(rules) >= 1
        assert "condition" in rules[0]
        assert "action" in rules[0]
    
    def test_pattern_stats(self):
        engine = PredictiveSymbiosisEngine()
        for i in range(10):
            engine.add_event({
                "event_type": "motion",
                "zone_id": "zone.lr",
                "timestamp": "2026-04-06T20:00:00Z"
            })
        engine.analyze_patterns()
        stats = engine.get_pattern_stats()
        assert stats["total_events"] == 10
        assert stats["total_patterns"] >= 1


class TestRuleOptimizer:
    def test_record_execution(self):
        from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine
        rule_engine = SymbioticRuleEngine()
        optimizer = RuleOptimizer(rule_engine)
        optimizer.record_execution("rule_1", {"zone": "lr"}, {"type": "light.on"})
        assert len(optimizer.execution_history) == 1
    
    def test_record_feedback(self):
        from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine
        rule_engine = SymbioticRuleEngine()
        optimizer = RuleOptimizer(rule_engine)
        optimizer.record_feedback("rule_1", True)
        assert optimizer.user_feedback["rule_1"] is True
    
    def test_score_all_rules(self):
        from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine
        rule_engine = SymbioticRuleEngine()
        rule_engine.register_rule("zone.lr", "motion", {}, {})
        rule_engine.rules["rule_1"]["triggered_count"] = 5
        
        optimizer = RuleOptimizer(rule_engine)
        optimizer.record_feedback("rule_1", True)
        
        scores = optimizer.score_all_rules()
        assert len(scores) == 1
        assert scores[0].rule_id == "rule_1"
        assert scores[0].utility_score == 1.0
    
    def test_get_optimization_suggestions(self):
        from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine
        rule_engine = SymbioticRuleEngine()
        rule_engine.register_rule("zone.lr", "motion", {}, {})
        
        optimizer = RuleOptimizer(rule_engine)
        suggestions = optimizer.get_optimization_suggestions()
        assert len(suggestions) >= 1  # Rule never triggered
        assert suggestions[0]["issue"] == "never_triggered"


class TestLearningMemorySync:
    def test_save_and_load_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sync = LearningMemorySync(tmpdir)
            patterns = [{"pattern_id": "p1", "data": "test"}]
            sync.save_patterns(patterns)
            loaded = sync.load_patterns()
            assert len(loaded) == 1
            assert loaded[0]["pattern_id"] == "p1"
    
    def test_save_and_load_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sync = LearningMemorySync(tmpdir)
            feedback = {"rule_1": True, "rule_2": False}
            sync.save_feedback(feedback)
            loaded = sync.load_feedback()
            assert loaded["rule_1"] is True
            assert loaded["rule_2"] is False
    
    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sync = LearningMemorySync(tmpdir)
            sync.save_patterns([{"pattern_id": "p1"}])
            sync.save_feedback({"rule_1": True})
            stats = sync.get_stats()
            assert stats["total_patterns"] == 1
            assert stats["total_feedback"] == 1
