"""Domain layer for Energy module.

Contains core business entities, value objects, and domain events.
No dependencies on external frameworks or infrastructure.
"""

from .entities import EnergyUsageEntry, ZoneEnergyPattern, EnergyEffectivenessMetrics
from .value_objects import (
    EnergyAmount,
    CostAmount,
    TariffRate,
    EnergySource,
    AnalyticsPeriod,
    TimestampRange,
)
from .events import (
    EnergyUsageRecorded,
    ZonePatternUpdated,
    MetricsCalculated,
)

__all__ = [
    # Entities
    "EnergyUsageEntry",
    "ZoneEnergyPattern",
    "EnergyEffectivenessMetrics",
    # Value Objects
    "EnergyAmount",
    "CostAmount",
    "TariffRate",
    "EnergySource",
    "AnalyticsPeriod",
    "TimestampRange",
    # Domain Events
    "EnergyUsageRecorded",
    "ZonePatternUpdated",
    "MetricsCalculated",
]
