"""Contract tests for the Energy Forecast Engine.

Verifies:
- EnergyForecastEngine, PVPredictionEngine, LoadShiftingEngine, SolarSurplusOptimizer
  initialize and have the expected public methods
- All energy engines can be instantiated and have their main computation methods
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


class TestEnergyForecastEngine:
    """EnergyForecastEngine contract."""

    def test_initializes(self):
        from copilot_core.energy.forecast import EnergyForecastEngine
        engine = EnergyForecastEngine()
        assert engine is not None

    def test_has_hourly_forecast_method(self):
        from copilot_core.energy.forecast import EnergyForecastEngine
        engine = EnergyForecastEngine()
        assert hasattr(engine, "generate_hourly_forecast")

    def test_has_daily_forecast_method(self):
        from copilot_core.energy.forecast import EnergyForecastEngine
        engine = EnergyForecastEngine()
        assert hasattr(engine, "generate_daily_forecast")

    def test_has_summary_method(self):
        from copilot_core.energy.forecast import EnergyForecastEngine
        engine = EnergyForecastEngine()
        assert hasattr(engine, "generate_summary")


class TestPVPredictionEngine:
    """PVPredictionEngine contract."""

    def test_initializes(self):
        from copilot_core.energy.pv_prediction import PVPredictionEngine
        engine = PVPredictionEngine()
        assert engine is not None

    def test_has_hourly_forecast_method(self):
        from copilot_core.energy.pv_prediction import PVPredictionEngine
        engine = PVPredictionEngine()
        assert hasattr(engine, "generate_hourly_forecast")

    def test_has_daily_forecast_method(self):
        from copilot_core.energy.pv_prediction import PVPredictionEngine
        engine = PVPredictionEngine()
        assert hasattr(engine, "generate_daily_forecast")


class TestLoadShiftingEngine:
    """LoadShiftingEngine contract."""

    def test_initializes(self):
        from copilot_core.energy.load_shifting import LoadShiftingEngine
        engine = LoadShiftingEngine()
        assert engine is not None

    def test_has_recommendations_method(self):
        from copilot_core.energy.load_shifting import LoadShiftingEngine
        engine = LoadShiftingEngine()
        assert hasattr(engine, "generate_recommendations")

    def test_has_optimization_windows_method(self):
        from copilot_core.energy.load_shifting import LoadShiftingEngine
        engine = LoadShiftingEngine()
        assert hasattr(engine, "generate_optimization_windows")


class TestSolarSurplusOptimizer:
    """SolarSurplusOptimizer contract."""

    def test_initializes(self):
        from copilot_core.energy.solar_surplus_optimizer import SolarSurplusOptimizer
        opt = SolarSurplusOptimizer()
        assert opt is not None

    def test_has_recommend_method(self):
        from copilot_core.energy.solar_surplus_optimizer import SolarSurplusOptimizer
        opt = SolarSurplusOptimizer()
        assert hasattr(opt, "recommend") or hasattr(opt, "get_recommendations_as_dict")


class TestShiftableDevice:
    """ShiftableDevice dataclass contract."""

    def test_shiftable_device_imports(self):
        from copilot_core.energy.load_shifting import ShiftableDevice
        assert ShiftableDevice is not None