"""Energy Service Sigma Calibration (Slice 192).

Replaces static percentage thresholds with dynamic sigma-deviation 
for high-load appliances to ensure statistical significance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

class EnergyService:
    """Core Service for energy monitoring and anomaly detection."""
    
    # SOTA Sigma Thresholds [low_warn, med_alert, high_critical]
    SIGMA_THRESHOLDS = {
        "washing_machine": [1.7, 1.9, 2.1],
        "dryer": [4.0, 4.5, 5.0],
        "heat_pump": [2.9, 3.3, 3.7],
        "ev_charger": [12.2, 13.4, 14.6],
        "default": [2.0, 3.0, 4.0]
    }

    def __init__(self):
        self._device_stats: Dict[str, Dict[str, float]] = {}

    def analyze_consumption(self, device_id: str, current_val: float, baseline_mean: float, stdev: float) -> Dict[str, Any]:
        """Analyzes consumption using appliance-specific sigma values."""
        if stdev == 0:
            return {"status": "normal", "sigma": 0.0}

        z_score = abs(current_val - baseline_mean) / stdev
        device_type = self._detect_device_type(device_id)
        thresholds = self.SIGMA_THRESHOLDS.get(device_type, self.SIGMA_THRESHOLDS["default"])
        
        status = "normal"
        if z_score >= thresholds[2]:
            status = "critical"
        elif z_score >= thresholds[1]:
            status = "alert"
        elif z_score >= thresholds[0]:
            status = "warning"
            
        _LOGGER.debug("Energy Sigma: %s (z=%.2f) -> %s", device_id, z_score, status)
        
        return {
            "device_id": device_id,
            "device_type": device_type,
            "z_score": round(z_score, 2),
            "status": status,
            "thresholds": thresholds
        }

    def _detect_device_type(self, device_id: str) -> str:
        """Heuristic for device type detection."""
        for key in self.SIGMA_THRESHOLDS.keys():
            if key in device_id.lower():
                return key
        return "default"

# Global Instance
_energy_service: Optional[EnergyService] = None

def get_energy_service() -> EnergyService:
    global _energy_service
    if _energy_service is None:
        _energy_service = EnergyService()
    return _energy_service

# API Extension
def init_energy_sigma_api(bp):
    @bp.route("/energy/sigma/thresholds", methods=["GET"])
    def get_thresholds():
        return {"ok": True, "thresholds": EnergyService.SIGMA_THRESHOLDS}
