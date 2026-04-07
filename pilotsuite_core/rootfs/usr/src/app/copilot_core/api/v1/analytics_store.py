"""Energy Analytics Store — simple in-memory storage for analytics data."""
from typing import Dict, Optional
from .analytics import (
    EnergyUsageHistoryV1,
    EnergyZonePatternsV1,
    EnergyEffectivenessMetricsV1,
)


class EnergyAnalyticsStore:
    """In-memory store for energy analytics data."""
    
    def __init__(self):
        self._history: Dict[str, EnergyUsageHistoryV1] = {}
        self._patterns: Dict[str, EnergyZonePatternsV1] = {}
        self._effectiveness: Optional[EnergyEffectivenessMetricsV1] = None
    
    def get_history(self, key: str) -> Optional[EnergyUsageHistoryV1]:
        return self._history.get(key)
    
    def set_history(self, key: str, history: EnergyUsageHistoryV1) -> None:
        self._history[key] = history
    
    def get_patterns(self, key: str) -> Optional[EnergyZonePatternsV1]:
        return self._patterns.get(key)
    
    def set_patterns(self, key: str, patterns: EnergyZonePatternsV1) -> None:
        self._patterns[key] = patterns
    
    def get_effectiveness(self) -> Optional[EnergyEffectivenessMetricsV1]:
        return self._effectiveness
    
    def set_effectiveness(self, metrics: EnergyEffectivenessMetricsV1) -> None:
        self._effectiveness = metrics


__all__ = ["EnergyAnalyticsStore"]
