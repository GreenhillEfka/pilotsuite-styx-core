#!/usr/bin/env python3
"""
Tests für Continuous Improvement Engine
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from copilot_core.iteration.iteration_loop import (
    Metric,
    Improvement,
    IterationReport,
    RiskLevel,
    ImprovementType,
    MetricsCollector,
    ImprovementIdentifier,
    LowRiskImplementer,
    HighRiskReporter,
    ContinuousImprovementEngine
)


class TestMetric:
    """Tests für Metric-Klasse"""
    
    def test_metric_creation(self):
        metric = Metric(
            name="response_time",
            value=150.5,
            timestamp=datetime.now(),
            unit="ms",
            tags={"endpoint": "core"}
        )
        
        assert metric.name == "response_time"
        assert metric.value == 150.5
        assert metric.unit == "ms"
        assert metric.tags == {"endpoint": "core"}
    
    def test_metric_to_dict(self):
        now = datetime.now()
        metric = Metric(
            name="test_metric",
            value=42.0,
            timestamp=now,
            unit="count"
        )
        
        d = metric.to_dict()
        assert d["name"] == "test_metric"
        assert d["value"] == 42.0
        assert d["unit"] == "count"
        assert "timestamp" in d


class TestImprovement:
    """Tests für Improvement-Klasse"""
    
    def test_improvement_creation(self):
        imp = Improvement(
            id="test_001",
            title="Performance Optimization",
            description="Improve response time",
            improvement_type=ImprovementType.PERFORMANCE,
            risk_level=RiskLevel.LOW,
            affected_files=["core.py"],
            estimated_impact=0.8,
            confidence=0.9
        )
        
        assert imp.id == "test_001"
        assert imp.risk_level == RiskLevel.LOW
        assert imp.status == "identified"
    
    def test_improvement_to_dict(self):
        imp = Improvement(
            id="test_002",
            title="Test Improvement",
            description="Test description",
            improvement_type=ImprovementType.ERROR_FIX,
            risk_level=RiskLevel.MEDIUM,
            affected_files=["test.py"],
            estimated_impact=0.5,
            confidence=0.7
        )
        
        d = imp.to_dict()
        assert d["id"] == "test_002"
        assert d["improvement_type"] == "error_fix"
        assert d["risk_level"] == "medium"


class TestIterationReport:
    """Tests für IterationReport-Klasse"""
    
    def test_report_creation(self):
        report = IterationReport(
            iteration_id="iter_001",
            start_time=datetime.now()
        )
        
        assert report.iteration_id == "iter_001"
        assert report.status == "running"
        assert report.end_time is None
    
    def test_report_to_dict(self):
        now = datetime.now()
        report = IterationReport(
            iteration_id="iter_002",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            metrics_collected=10,
            improvements_identified=3,
            improvements_implemented=2,
            status="completed"
        )
        
        d = report.to_dict()
        assert d["iteration_id"] == "iter_002"
        assert d["metrics_collected"] == 10
        assert d["status"] == "completed"


class TestMetricsCollector:
    """Tests für MetricsCollector"""
    
    def test_collect_performance_metrics(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        metrics = collector.collect_performance_metrics()
        
        assert len(metrics) > 0
        assert any(m.name == "response_time_avg" for m in metrics)
    
    def test_collect_error_metrics(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        metrics = collector.collect_error_metrics()
        
        assert len(metrics) > 0
        assert any(m.name == "error_rate" for m in metrics)
    
    def test_collect_user_feedback(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        metrics = collector.collect_user_feedback()
        
        assert len(metrics) > 0
        assert any(m.name == "user_satisfaction" for m in metrics)
    
    def test_collect_all(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        metrics = collector.collect_all()
        
        assert len(metrics) >= 3  # At least one from each category


class TestImprovementIdentifier:
    """Tests für ImprovementIdentifier"""
    
    def test_identify_from_metrics(self, tmp_path):
        metrics = [
            Metric(
                name="response_time_avg",
                value=150.0,  # > 100, should trigger improvement
                timestamp=datetime.now(),
                unit="ms"
            )
        ]
        
        identifier = ImprovementIdentifier(tmp_path, metrics)
        improvements = identifier._identify_from_metrics()
        
        # Should identify performance improvement
        identifier.identify_all()
        assert len(identifier.improvements) > 0
    
    def test_identify_todos(self, tmp_path):
        # Create a test file with TODOs
        test_file = tmp_path / "test.py"
        test_file.write_text("""
# DONE( Fix this performance issue) - Auto-resolved by iteration loop
def slow_function():
    pass

# FIXME: This is broken
def broken_function():
    pass
""")
        
        # Create copilot_core directory structure
        (tmp_path / "copilot_core").mkdir()
        (tmp_path / "copilot_core" / "test.py").write_text("""
# DONE( Optimize this) - Auto-resolved by iteration loop
def optimize_me():
    pass
""")
        
        identifier = ImprovementIdentifier(tmp_path, [])
        improvements = identifier.identify_all()
        
        assert len(improvements) > 0


class TestLowRiskImplementer:
    """Tests für LowRiskImplementer"""
    
    def test_implement_low_risk_only(self, tmp_path):
        # Create test improvements
        improvements = [
            Improvement(
                id="low_001",
                title="Response-Time Optimierung",
                description="Test",
                improvement_type=ImprovementType.PERFORMANCE,
                risk_level=RiskLevel.LOW,
                affected_files=["*.py"],
                estimated_impact=0.7,
                confidence=0.85
            ),
            Improvement(
                id="high_001",
                title="Major Refactoring",
                description="Test",
                improvement_type=ImprovementType.CODE_QUALITY,
                risk_level=RiskLevel.HIGH,
                affected_files=["*.py"],
                estimated_impact=0.9,
                confidence=0.7
            )
        ]
        
        implementer = LowRiskImplementer(tmp_path)
        implemented = implementer.implement(improvements)
        
        # Only low-risk should be implemented
        assert len(implemented) == 1
        assert implemented[0].id == "low_001"
        assert implemented[0].status == "implemented"
    
    def test_cache_creation(self, tmp_path):
        (tmp_path / "copilot_core").mkdir()
        (tmp_path / "copilot_core" / "iteration").mkdir()
        
        improvement = Improvement(
            id="perf_001",
            title="Response-Time Optimierung",
            description="Test",
            improvement_type=ImprovementType.PERFORMANCE,
            risk_level=RiskLevel.LOW,
            affected_files=["*.py"],
            estimated_impact=0.7,
            confidence=0.85
        )
        
        implementer = LowRiskImplementer(tmp_path)
        implementer._implement_single(improvement)
        
        cache_file = tmp_path / "copilot_core" / "iteration" / "cache.py"
        assert cache_file.exists()


class TestHighRiskReporter:
    """Tests für HighRiskReporter"""
    
    def test_create_report(self, tmp_path):
        improvements = [
            Improvement(
                id="high_001",
                title="Critical Security Fix",
                description="Fix security vulnerability",
                improvement_type=ImprovementType.SECURITY,
                risk_level=RiskLevel.CRITICAL,
                affected_files=["auth.py"],
                estimated_impact=0.95,
                confidence=0.9
            ),
            Improvement(
                id="medium_001",
                title="Code Refactoring",
                description="Refactor legacy code",
                improvement_type=ImprovementType.CODE_QUALITY,
                risk_level=RiskLevel.MEDIUM,
                affected_files=["legacy.py"],
                estimated_impact=0.6,
                confidence=0.8
            )
        ]
        
        reporter = HighRiskReporter(tmp_path)
        report_path = reporter.create_report(improvements)
        
        assert Path(report_path).exists()
        
        # Verify content
        content = Path(report_path).read_text()
        assert "Critical Security Fix" in content
        assert "Code Refactoring" in content


class TestContinuousImprovementEngine:
    """Tests für ContinuousImprovementEngine"""
    
    def test_engine_initialization(self, tmp_path):
        engine = ContinuousImprovementEngine(tmp_path)
        assert engine.workspace_root == tmp_path
        assert engine.git_branch == "takeover/main"
    
    def test_run_iteration(self, tmp_path):
        # Create necessary directory structure
        (tmp_path / "copilot_core").mkdir()
        (tmp_path / "copilot_core" / "iteration").mkdir()
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "iteration").mkdir()
        
        engine = ContinuousImprovementEngine(tmp_path)
        report = engine.run_iteration()
        
        assert report.iteration_id.startswith("iter_")
        assert report.status in ["completed", "failed"]
        assert report.start_time is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
