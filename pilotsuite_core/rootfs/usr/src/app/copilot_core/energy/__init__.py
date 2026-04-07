"""Energy Neuron for PilotSuite Core.

Provides energy monitoring, anomaly detection, load shifting, and forecasting.
"""
from .service import EnergyService
from .forecast import EnergyForecastEngine, ForecastDataPoint, DailyForecast, ForecastSummary
from .pv_prediction import PVPredictionEngine, PVHourlyForecast, PVDailyForecast, PVForecastSummary
from .load_shifting import (
    LoadShiftingEngine,
    ShiftableDevice,
    LoadShiftRecommendation,
    OptimizationWindow,
    LoadShiftSummary,
)
from .optimization_engine import (
    EnergyOptimizationEngine,
    EnergyReading,
    EnergyUnit,
    OptimizationType,
    OptimizationSuggestion,
    TariffPeriod,
    create_energy_optimization_engine,
)

# Global service instance for API access
_energy_service = None


def set_energy_service(service: EnergyService):
    """Set the global energy service instance."""
    global _energy_service
    _energy_service = service


def get_energy_service() -> EnergyService:
    """Get the global energy service instance."""
    return _energy_service


__all__ = [
    # Service
    "EnergyService",
    "set_energy_service",
    "get_energy_service",
    # Forecast
    "EnergyForecastEngine",
    "ForecastDataPoint",
    "DailyForecast",
    "ForecastSummary",
    # PV Prediction
    "PVPredictionEngine",
    "PVHourlyForecast",
    "PVDailyForecast",
    "PVForecastSummary",
    # Load Shifting
    "LoadShiftingEngine",
    "ShiftableDevice",
    "LoadShiftRecommendation",
    "OptimizationWindow",
    "LoadShiftSummary",
    # Optimization
    "EnergyOptimizationEngine",
    "EnergyReading",
    "EnergyUnit",
    "OptimizationType",
    "OptimizationSuggestion",
    "TariffPeriod",
    "create_energy_optimization_engine",
]
__version__ = "1.0.0"
