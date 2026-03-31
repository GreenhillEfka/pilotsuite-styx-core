"""Camera & Security Integration — Slice 17.

Camera surveillance and security monitoring for PilotSuite Core.

Features:
- Camera stream management
- Motion detection integration
- Security zone monitoring
- Alert generation on suspicious activity
- Snapshot capture and storage
- Person/package detection integration
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security level for zones."""
    LOW = "low"  # No security concerns
    MEDIUM = "medium"  # Normal monitoring
    HIGH = "high"  # Enhanced monitoring
    CRITICAL = "critical"  # Active threat detected


class AlertType(Enum):
    """Type of security alert."""
    MOTION_DETECTED = "motion_detected"
    PERSON_DETECTED = "person_detected"
    PACKAGE_DETECTED = "package_detected"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    CAMERA_OFFLINE = "camera_offline"
    CAMERA_TAMPERED = "camera_tampered"
    SECURITY_BREACH = "security_breach"


class AlertSeverity(Enum):
    """Severity of security alert."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CameraConfig:
    """Camera configuration."""
    camera_id: str
    name: str
    zone_id: str
    entity_id: str  # HA camera entity
    stream_url: Optional[str] = None
    snapshot_url: Optional[str] = None
    motion_entity_id: Optional[str] = None
    enabled: bool = True
    recording_enabled: bool = False
    night_vision: bool = False
    last_seen: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "zone_id": self.zone_id,
            "entity_id": self.entity_id,
            "stream_url": self.stream_url,
            "snapshot_url": self.snapshot_url,
            "motion_entity_id": self.motion_entity_id,
            "enabled": self.enabled,
            "recording_enabled": self.recording_enabled,
            "night_vision": self.night_vision,
            "last_seen": self.last_seen,
        }


@dataclass
class SecurityAlert:
    """Security alert from camera/zone monitoring."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    camera_id: Optional[str]
    zone_id: str
    description: str
    snapshot_url: Optional[str] = None
    video_url: Optional[str] = None
    acknowledged: bool = False
    resolved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "description": self.description,
            "snapshot_url": self.snapshot_url,
            "video_url": self.video_url,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "created_at": self.created_at,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }


@dataclass
class SecuritySnapshot:
    """Captured security snapshot."""
    snapshot_id: str
    camera_id: str
    zone_id: str
    image_url: str
    thumbnail_url: Optional[str] = None
    motion_detected: bool = False
    person_detected: bool = False
    package_detected: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    storage_path: Optional[str] = None
    retention_days: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "motion_detected": self.motion_detected,
            "person_detected": self.person_detected,
            "package_detected": self.package_detected,
            "created_at": self.created_at,
            "storage_path": self.storage_path,
            "retention_days": self.retention_days,
        }


class CameraSecurityEngine:
    """Camera and security monitoring engine."""
    
    def __init__(self):
        self._cameras: Dict[str, CameraConfig] = {}
        self._alerts: Dict[str, SecurityAlert] = {}
        self._snapshots: Dict[str, SecuritySnapshot] = {}
        self._zone_security_levels: Dict[str, SecurityLevel] = {}
        self._alert_counter = 0
        self._snapshot_counter = 0
        
        # Alert thresholds
        self._motion_cooldown_seconds = 60  # Min time between motion alerts
        self._last_motion_alert: Dict[str, datetime] = {}
    
    def register_camera(self, config: Dict[str, Any]) -> str:
        """Register a new camera."""
        camera = CameraConfig(
            camera_id=config.get("camera_id", f"cam_{len(self._cameras) + 1}"),
            name=config.get("name", "Unknown Camera"),
            zone_id=config.get("zone_id", "unknown"),
            entity_id=config.get("entity_id", ""),
            stream_url=config.get("stream_url"),
            snapshot_url=config.get("snapshot_url"),
            motion_entity_id=config.get("motion_entity_id"),
            enabled=config.get("enabled", True),
            recording_enabled=config.get("recording_enabled", False),
            night_vision=config.get("night_vision", False),
        )
        
        self._cameras[camera.camera_id] = camera
        
        # Initialize zone security level
        if camera.zone_id not in self._zone_security_levels:
            self._zone_security_levels[camera.zone_id] = SecurityLevel.MEDIUM
        
        return camera.camera_id
    
    def process_motion_event(self, camera_id: str, motion_detected: bool) -> Optional[SecurityAlert]:
        """Process motion detection event from camera."""
        if camera_id not in self._cameras:
            return None
        
        camera = self._cameras[camera_id]
        
        if not camera.enabled:
            return None
        
        # Update last seen
        camera.last_seen = datetime.now(timezone.utc).isoformat()
        
        if not motion_detected:
            return None
        
        # Check cooldown
        now = datetime.now(timezone.utc)
        last_alert = self._last_motion_alert.get(camera_id)
        if last_alert and (now - last_alert).total_seconds() < self._motion_cooldown_seconds:
            return None
        
        self._last_motion_alert[camera_id] = now
        
        # Create alert
        self._alert_counter += 1
        alert = SecurityAlert(
            alert_id=f"alert_{self._alert_counter}",
            alert_type=AlertType.MOTION_DETECTED,
            severity=AlertSeverity.INFO,
            camera_id=camera_id,
            zone_id=camera.zone_id,
            description=f"Motion detected by {camera.name}",
            metadata={"camera_name": camera.name, "zone": camera.zone_id},
        )
        
        self._alerts[alert.alert_id] = alert
        
        # Capture snapshot
        self._capture_snapshot(camera_id, motion_detected=True)
        
        # Elevate zone security level temporarily
        self._zone_security_levels[camera.zone_id] = SecurityLevel.HIGH
        
        return alert
    
    def process_person_detection(self, camera_id: str, confidence: float = 0.0) -> Optional[SecurityAlert]:
        """Process person detection event."""
        if camera_id not in self._cameras:
            return None
        
        camera = self._cameras[camera_id]
        
        if not camera.enabled:
            return None
        
        self._alert_counter += 1
        severity = AlertSeverity.WARNING if confidence > 0.8 else AlertSeverity.INFO
        
        alert = SecurityAlert(
            alert_id=f"alert_{self._alert_counter}",
            alert_type=AlertType.PERSON_DETECTED,
            severity=severity,
            camera_id=camera_id,
            zone_id=camera.zone_id,
            description=f"Person detected by {camera.name} (confidence: {confidence:.0%})",
            metadata={"confidence": confidence, "camera_name": camera.name},
        )
        
        self._alerts[alert.alert_id] = alert
        self._capture_snapshot(camera_id, person_detected=True)
        
        return alert
    
    def process_package_detection(self, camera_id: str) -> Optional[SecurityAlert]:
        """Process package detection event."""
        if camera_id not in self._cameras:
            return None
        
        camera = self._cameras[camera_id]
        
        if not camera.enabled:
            return None
        
        self._alert_counter += 1
        alert = SecurityAlert(
            alert_id=f"alert_{self._alert_counter}",
            alert_type=AlertType.PACKAGE_DETECTED,
            severity=AlertSeverity.INFO,
            camera_id=camera_id,
            zone_id=camera.zone_id,
            description=f"Package detected by {camera.name}",
            metadata={"camera_name": camera.name},
        )
        
        self._alerts[alert.alert_id] = alert
        self._capture_snapshot(camera_id, package_detected=True)
        
        return alert
    
    def _capture_snapshot(self, camera_id: str, motion_detected: bool = False,
                         person_detected: bool = False, package_detected: bool = False) -> Optional[SecuritySnapshot]:
        """Capture security snapshot."""
        if camera_id not in self._cameras:
            return None
        
        camera = self._cameras[camera_id]
        
        self._snapshot_counter += 1
        snapshot = SecuritySnapshot(
            snapshot_id=f"snapshot_{self._snapshot_counter}",
            camera_id=camera_id,
            zone_id=camera.zone_id,
            image_url=f"/api/camera/{camera_id}/snapshot/{self._snapshot_counter}",
            motion_detected=motion_detected,
            person_detected=person_detected,
            package_detected=package_detected,
            storage_path=f"/data/camera/{camera_id}/{self._snapshot_counter}.jpg",
        )
        
        self._snapshots[snapshot.snapshot_id] = snapshot
        return snapshot
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a security alert."""
        if alert_id not in self._alerts:
            return False
        
        alert = self._alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
        return True
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve a security alert."""
        if alert_id not in self._alerts:
            return False
        
        alert = self._alerts[alert_id]
        alert.resolved = True
        alert.resolved_at = datetime.now(timezone.utc).isoformat()
        
        # Reset zone security level if no other active alerts
        active_alerts = [a for a in self._alerts.values() if not a.resolved and a.zone_id == alert.zone_id]
        if not active_alerts:
            self._zone_security_levels[alert.zone_id] = SecurityLevel.MEDIUM
        
        return True
    
    def get_alerts(self, zone_id: Optional[str] = None, unresolved_only: bool = True,
                   limit: int = 50) -> List[Dict[str, Any]]:
        """Get security alerts."""
        alerts = list(self._alerts.values())
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        if zone_id:
            alerts = [a for a in alerts if a.zone_id == zone_id]
        
        # Sort by created_at (newest first)
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return [a.to_dict() for a in alerts[:limit]]
    
    def get_snapshots(self, camera_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get security snapshots."""
        snapshots = list(self._snapshots.values())
        
        if camera_id:
            snapshots = [s for s in snapshots if s.camera_id == camera_id]
        
        # Sort by created_at (newest first)
        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        
        return [s.to_dict() for s in snapshots[:limit]]
    
    def get_cameras(self, zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get registered cameras."""
        cameras = list(self._cameras.values())
        
        if zone_id:
            cameras = [c for c in cameras if c.zone_id == zone_id]
        
        return [c.to_dict() for c in cameras]
    
    def get_zone_security_level(self, zone_id: str) -> SecurityLevel:
        """Get current security level for a zone."""
        return self._zone_security_levels.get(zone_id, SecurityLevel.MEDIUM)
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get overall security summary."""
        total_alerts = len(self._alerts)
        unresolved_alerts = len([a for a in self._alerts.values() if not a.resolved])
        critical_alerts = len([a for a in self._alerts.values() 
                              if not a.resolved and a.severity == AlertSeverity.CRITICAL])
        
        total_snapshots = len(self._snapshots)
        active_cameras = len([c for c in self._cameras.values() if c.enabled])
        
        return {
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "critical_alerts": critical_alerts,
            "total_snapshots": total_snapshots,
            "active_cameras": active_cameras,
            "total_cameras": len(self._cameras),
            "zones_monitored": len(self._zone_security_levels),
        }


def create_camera_security_engine() -> CameraSecurityEngine:
    """Factory function to create camera security engine."""
    return CameraSecurityEngine()
