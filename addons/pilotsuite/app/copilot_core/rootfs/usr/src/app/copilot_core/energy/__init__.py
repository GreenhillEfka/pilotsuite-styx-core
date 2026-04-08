"""Energy Neuron for PilotSuite Core.

Provides energy monitoring, anomaly detection, and load shifting opportunities.
"""
from .service import EnergyService

# Global service instance for API access
_energy_service = None


def set_energy_service(service: EnergyService):
    """Set the global energy service instance."""
    global _energy_service
    _energy_service = service


def get_energy_service() -> EnergyService:
    """Get the global energy service instance."""
    return _energy_service


__all__ = ["EnergyService", "set_energy_service", "get_energy_service"]
__version__ = "0.4.11"
