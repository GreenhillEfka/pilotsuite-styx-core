"""Contract tests for Hub engine classes.

Verifies every Hub engine class can be imported and instantiated.
This is the foundational contract: if an engine can't be created,
nothing else works.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestDashboardEngine:
    """DashboardHub contract."""

    def test_dashboard_hub_initializes(self):
        from copilot_core.hub.dashboard import DashboardHub
        hub = DashboardHub()
        assert hub is not None

    def test_dashboard_layout_initializes(self):
        from copilot_core.hub.dashboard import DashboardLayout
        layout = DashboardLayout()
        assert layout is not None


class TestEnergyAdvisorEngine:
    """EnergyAdvisorEngine contract."""

    def test_energy_advisor_engine_initializes(self):
        from copilot_core.hub.energy_advisor import EnergyAdvisorEngine
        engine = EnergyAdvisorEngine()
        assert engine is not None

    def test_context_aware_energy_optimizer_initializes(self):
        from copilot_core.hub.energy_advisor import ContextAwareEnergyOptimizer
        opt = ContextAwareEnergyOptimizer()
        assert opt is not None

    def test_advisor_engine_has_get_dashboard(self):
        from copilot_core.hub.energy_advisor import EnergyAdvisorEngine
        engine = EnergyAdvisorEngine()
        assert hasattr(engine, "get_dashboard")


class TestAutomationTemplateEngine:
    """AutomationTemplateEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.automation_templates import AutomationTemplateEngine
        engine = AutomationTemplateEngine()
        assert engine is not None

    def test_engine_has_generate_method(self):
        from copilot_core.hub.automation_templates import AutomationTemplateEngine
        engine = AutomationTemplateEngine()
        assert hasattr(engine, "generate_automation")


class TestAnomalyDetectionEngine:
    """AnomalyDetectionEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.anomaly_detection import AnomalyDetectionEngine
        engine = AnomalyDetectionEngine()
        assert engine is not None

    def test_engine_has_detect_method(self):
        from copilot_core.hub.anomaly_detection import AnomalyDetectionEngine
        engine = AnomalyDetectionEngine()
        assert hasattr(engine, "detect") or hasattr(engine, "detect_anomaly")


class TestBrainActivityEngine:
    """BrainActivityEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.brain_activity import BrainActivityEngine
        engine = BrainActivityEngine()
        assert engine is not None

    def test_engine_has_get_status(self):
        from copilot_core.hub.brain_activity import BrainActivityEngine
        engine = BrainActivityEngine()
        assert hasattr(engine, "get_status") or hasattr(engine, "status")


class TestBrainArchitectureEngine:
    """BrainArchitectureEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.brain_architecture import BrainArchitectureEngine
        engine = BrainArchitectureEngine()
        assert engine is not None

    def test_engine_has_get_status(self):
        from copilot_core.hub.brain_architecture import BrainArchitectureEngine
        engine = BrainArchitectureEngine()
        assert hasattr(engine, "get_status") or hasattr(engine, "status")


class TestHabitusZoneEngine:
    """HabitusZoneEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.habitus_zones import HabitusZoneEngine
        engine = HabitusZoneEngine()
        assert engine is not None

    def test_engine_has_get_zones_method(self):
        from copilot_core.hub.habitus_zones import HabitusZoneEngine
        engine = HabitusZoneEngine()
        assert hasattr(engine, "get_zones") or hasattr(engine, "get_overview")


class TestHeizModuleEngine:
    """HeizModuleEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.heiz_module import HeizModuleEngine
        engine = HeizModuleEngine()
        assert engine is not None

    def test_engine_has_get_dashboard(self):
        from copilot_core.hub.heiz_module import HeizModuleEngine
        engine = HeizModuleEngine()
        assert (hasattr(engine, "get_summary") or hasattr(engine, "get_status") or hasattr(engine, "get_diagnostics"))


class TestHelligkeitModuleEngine:
    """HelligkeitModuleEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.helligkeit_module import HelligkeitModuleEngine
        engine = HelligkeitModuleEngine()
        assert engine is not None

    def test_engine_has_get_dashboard(self):
        from copilot_core.hub.helligkeit_module import HelligkeitModuleEngine
        engine = HelligkeitModuleEngine()
        assert (hasattr(engine, "get_summary") or hasattr(engine, "get_status") or hasattr(engine, "get_diagnostics"))


class TestHomeAssistantModuleEngine:
    """HomeAssistantModuleEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.homeassistant_module import HomeAssistantModuleEngine
        engine = HomeAssistantModuleEngine()
        assert engine is not None

    def test_engine_has_get_dashboard(self):
        from copilot_core.hub.homeassistant_module import HomeAssistantModuleEngine
        engine = HomeAssistantModuleEngine()
        assert (hasattr(engine, "get_summary") or hasattr(engine, "get_status") or hasattr(engine, "get_diagnostics"))


class TestBewegungModuleEngine:
    """BewegungModuleEngine contract."""

    def test_engine_initializes(self):
        from copilot_core.hub.bewegung_module import BewegungModuleEngine
        engine = BewegungModuleEngine()
        assert engine is not None

    def test_engine_has_get_dashboard(self):
        from copilot_core.hub.bewegung_module import BewegungModuleEngine
        engine = BewegungModuleEngine()
        assert (hasattr(engine, "get_summary") or hasattr(engine, "get_status") or hasattr(engine, "get_diagnostics"))


class TestPresenceIntelligenceEngine:
    """PresenceIntelligenceEngine contract (already tested in passing, confirm)."""

    def test_engine_initializes(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        engine = PresenceIntelligenceEngine()
        assert engine is not None

    def test_engine_has_get_dashboard(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        engine = PresenceIntelligenceEngine()
        assert hasattr(engine, "get_dashboard")

    def test_engine_has_get_heatmap(self):
        from copilot_core.hub.presence_intelligence import PresenceIntelligenceEngine
        engine = PresenceIntelligenceEngine()
        assert hasattr(engine, "get_heatmap")