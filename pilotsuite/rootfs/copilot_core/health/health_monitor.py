"""Health Monitor — System + Zone + Device Health (SOTA 2026).

3-Layer Health Monitoring:
1. Device Health — Einzelne Geräte/Entities
2. Zone Health — Aggregiert pro Zone
3. System Health — Gesamt-System

Metrics:
- Availability (online/offline)
- Response Time
- Error Rate
- Battery Level
- Signal Strength (RSSI/LQI)
- Last Seen

Integration:
- Health → Automation (bei schlechter Health pausieren)
- Health → Dashboard (Visualisierung)
- Health → Alerts (Benachrichtigungen)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import threading
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# HEALTH STATUS
# =============================================================================

class HealthStatus(str, Enum):
    """Health Status."""
    
    HEALTHY = "healthy"      # Alles OK
    DEGRADED = "degraded"    # Leichte Probleme
    UNHEALTHY = "unhealthy"  # Kritische Probleme
    OFFLINE = "offline"      # Nicht erreichbar


@dataclass
class DeviceHealth:
    """Health eines einzelnen Geräts."""
    
    device_id: str
    device_type: str
    zone_id: Optional[str] = None
    status: HealthStatus = HealthStatus.HEALTHY
    availability: float = 1.0  # 0-1
    response_time_ms: float = 0.0
    error_rate: float = 0.0  # 0-1
    battery_level: Optional[float] = None  # 0-1
    signal_strength: Optional[float] = None  # RSSI/LQI normalized 0-1
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "zone_id": self.zone_id,
            "status": self.status.value,
            "availability": round(self.availability, 3),
            "response_time_ms": round(self.response_time_ms, 2),
            "error_rate": round(self.error_rate * 100, 1),
            "battery_level": round(self.battery_level * 100, 0) if self.battery_level else None,
            "signal_strength": round(self.signal_strength * 100, 0) if self.signal_strength else None,
            "last_seen": self.last_seen,
            "last_error": self.last_error,
        }
    
    def calculate_health_score(self) -> float:
        """Health Score berechnen (0-1)."""
        weights = {
            "availability": 0.30,
            "response_time": 0.20,
            "error_rate": 0.20,
            "battery": 0.15,
            "signal": 0.15,
        }
        
        score = 0.0
        
        # Availability
        score += self.availability * weights["availability"]
        
        # Response time (<100ms = 1.0, >1000ms = 0.0)
        response_score = max(0.0, 1.0 - self.response_time_ms / 1000.0)
        score += response_score * weights["response_time"]
        
        # Error rate (0% = 1.0, 100% = 0.0)
        score += (1.0 - self.error_rate) * weights["error_rate"]
        
        # Battery (if available)
        if self.battery_level is not None:
            score += self.battery_level * weights["battery"]
        else:
            score += 0.5 * weights["battery"]  # Neutral if unknown
        
        # Signal (if available)
        if self.signal_strength is not None:
            score += self.signal_strength * weights["signal"]
        else:
            score += 0.5 * weights["signal"]
        
        return max(0.0, min(1.0, score))


@dataclass
class ZoneHealth:
    """Health einer Zone (aggregiert)."""
    
    zone_id: str
    zone_name: str
    device_count: int = 0
    healthy_devices: int = 0
    degraded_devices: int = 0
    unhealthy_devices: int = 0
    offline_devices: int = 0
    health_score: float = 0.0
    status: HealthStatus = HealthStatus.HEALTHY
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemHealth:
    """Gesamt-System Health."""
    
    total_devices: int = 0
    total_zones: int = 0
    healthy_zones: int = 0
    degraded_zones: int = 0
    unhealthy_zones: int = 0
    health_score: float = 0.0
    status: HealthStatus = HealthStatus.HEALTHY
    uptime_hours: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# HEALTH MONITOR
# =============================================================================

class HealthMonitor:
    """Health Monitoring Engine."""
    
    def __init__(self):
        self._devices: Dict[str, DeviceHealth] = {}
        self._zones: Dict[str, ZoneHealth] = {}
        self._system_start = datetime.now(timezone.utc)
        self._alert_hooks = []
        self._lock = threading.Lock()
        _LOGGER.info("HealthMonitor initialized")
    
    def update_device_health(self, health: DeviceHealth) -> None:
        """Device Health updaten."""
        with self._lock:
            old_health = self._devices.get(health.device_id)
            self._devices[health.device_id] = health
            
            # Check for status change (alert if degraded/unhealthy)
            if old_health and old_health.status != health.status:
                if health.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]:
                    self._trigger_alert(health.device_id, health)
            
            # Update zone health
            if health.zone_id:
                self._update_zone_health(health.zone_id)
    
    def get_device_health(self, device_id: str) -> Optional[DeviceHealth]:
        """Device Health holen."""
        with self._lock:
            return self._devices.get(device_id)
    
    def get_zone_health(self, zone_id: str) -> Optional[ZoneHealth]:
        """Zone Health holen."""
        with self._lock:
            return self._zones.get(zone_id)
    
    def get_system_health(self) -> SystemHealth:
        """System Health holen."""
        with self._lock:
            zone_healths = list(self._zones.values())
            
            healthy = sum(1 for z in zone_healths if z.status == HealthStatus.HEALTHY)
            degraded = sum(1 for z in zone_healths if z.status == HealthStatus.DEGRADED)
            unhealthy = sum(1 for z in zone_healths if z.status == HealthStatus.UNHEALTHY)
            
            avg_score = sum(z.health_score for z in zone_healths) / max(len(zone_healths), 1)
            
            if avg_score >= 0.8:
                status = HealthStatus.HEALTHY
            elif avg_score >= 0.5:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            uptime = (datetime.now(timezone.utc) - self._system_start).total_seconds() / 3600.0
            
            return SystemHealth(
                total_devices=len(self._devices),
                total_zones=len(self._zones),
                healthy_zones=healthy,
                degraded_zones=degraded,
                unhealthy_zones=unhealthy,
                health_score=avg_score,
                status=status,
                uptime_hours=round(uptime, 2),
            )
    
    def _update_zone_health(self, zone_id: str) -> None:
        """Zone Health aktualisieren (aus Devices aggregieren)."""
        zone_devices = [
            d for d in self._devices.values()
            if d.zone_id == zone_id
        ]
        
        if not zone_devices:
            return
        
        healthy = sum(1 for d in zone_devices if d.status == HealthStatus.HEALTHY)
        degraded = sum(1 for d in zone_devices if d.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for d in zone_devices if d.status == HealthStatus.UNHEALTHY)
        offline = sum(1 for d in zone_devices if d.status == HealthStatus.OFFLINE)
        
        avg_score = sum(d.calculate_health_score() for d in zone_devices) / len(zone_devices)
        
        if avg_score >= 0.8:
            status = HealthStatus.HEALTHY
        elif avg_score >= 0.5:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY
        
        zone_health = ZoneHealth(
            zone_id=zone_id,
            zone_name=zone_id,
            device_count=len(zone_devices),
            healthy_devices=healthy,
            degraded_devices=degraded,
            unhealthy_devices=unhealthy,
            offline_devices=offline,
            health_score=round(avg_score, 3),
            status=status,
        )
        
        self._zones[zone_id] = zone_health
    
    def _trigger_alert(self, device_id: str, health: DeviceHealth) -> None:
        """Alert auslösen."""
        for hook in self._alert_hooks:
            try:
                hook(device_id, health)
            except Exception as e:
                _LOGGER.error(f"Alert hook error: {e}")
    
    def register_alert_hook(self, hook) -> None:
        """Hook für Health Alerts."""
        self._alert_hooks.append(hook)
    
    def get_all_device_health(self) -> Dict[str, Dict[str, Any]]:
        """Alle Device Health."""
        with self._lock:
            return {
                device_id: health.to_dict()
                for device_id, health in self._devices.items()
            }
    
    def get_all_zone_health(self) -> Dict[str, Dict[str, Any]]:
        """Alle Zone Health."""
        with self._lock:
            return {
                zone_id: health.to_dict()
                for zone_id, health in self._zones.items()
            }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Dashboard Daten."""
        system = self.get_system_health()
        
        return {
            "system": system.to_dict(),
            "zones": self.get_all_zone_health(),
            "devices": {
                "total": len(self._devices),
                "by_status": {
                    "healthy": sum(1 for d in self._devices.values() if d.status == HealthStatus.HEALTHY),
                    "degraded": sum(1 for d in self._devices.values() if d.status == HealthStatus.DEGRADED),
                    "unhealthy": sum(1 for d in self._devices.values() if d.status == HealthStatus.UNHEALTHY),
                    "offline": sum(1 for d in self._devices.values() if d.status == HealthStatus.OFFLINE),
                },
            },
        }
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_devices": len(self._devices),
                "total_zones": len(self._zones),
                "alert_hooks": len(self._alert_hooks),
                "uptime_hours": (datetime.now(timezone.utc) - self._system_start).total_seconds() / 3600.0,
            }


# =============================================================================
# Singleton
# =============================================================================

_monitor_instance: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Singleton-Zugriff."""
    global _monitor_instance
    
    if _monitor_instance is None:
        _monitor_instance = HealthMonitor()
    
    return _monitor_instance
