"""Tests for Camera & Security Engine — Slice 17."""
import pytest
from copilot_core.camera.security_engine import (
    CameraSecurityEngine,
    SecurityLevel,
    AlertType,
    AlertSeverity,
    SecurityAlert,
    SecuritySnapshot,
    create_camera_security_engine,
)


class TestCameraSecurityEngine:
    """Test camera security engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_camera_security_engine()
        assert engine is not None
    
    def test_register_camera(self):
        """Test camera registration."""
        engine = CameraSecurityEngine()
        
        camera_id = engine.register_camera({
            "name": "Front Door",
            "zone_id": "zone_entrance",
            "entity_id": "camera.front_door",
            "enabled": True,
        })
        
        assert camera_id is not None
        assert camera_id in engine._cameras
        assert engine._cameras[camera_id].name == "Front Door"
        assert engine._cameras[camera_id].zone_id == "zone_entrance"
    
    def test_process_motion_event(self):
        """Test motion event processing."""
        engine = CameraSecurityEngine()
        
        # Register camera
        engine.register_camera({
            "name": "Living Room",
            "zone_id": "zone_living_room",
            "entity_id": "camera.living_room",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Process motion
        alert = engine.process_motion_event(camera_id, motion_detected=True)
        
        assert alert is not None
        assert alert.alert_type == AlertType.MOTION_DETECTED
        assert alert.zone_id == "zone_living_room"
    
    def test_motion_cooldown(self):
        """Test motion alert cooldown."""
        engine = CameraSecurityEngine()
        engine._motion_cooldown_seconds = 1  # 1 second for testing
        
        engine.register_camera({
            "name": "Test Cam",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # First motion should create alert
        alert1 = engine.process_motion_event(camera_id, motion_detected=True)
        assert alert1 is not None
        
        # Second motion immediately should be blocked by cooldown
        alert2 = engine.process_motion_event(camera_id, motion_detected=True)
        assert alert2 is None
    
    def test_process_person_detection(self):
        """Test person detection processing."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Driveway",
            "zone_id": "zone_driveway",
            "entity_id": "camera.driveway",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Process person detection with high confidence
        alert = engine.process_person_detection(camera_id, confidence=0.95)
        
        assert alert is not None
        assert alert.alert_type == AlertType.PERSON_DETECTED
        assert alert.severity == AlertSeverity.WARNING  # High confidence = warning
    
    def test_process_person_detection_low_confidence(self):
        """Test person detection with low confidence."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Garden",
            "zone_id": "zone_garden",
            "entity_id": "camera.garden",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Process person detection with low confidence
        alert = engine.process_person_detection(camera_id, confidence=0.5)
        
        assert alert is not None
        assert alert.alert_type == AlertType.PERSON_DETECTED
        assert alert.severity == AlertSeverity.INFO  # Low confidence = info
    
    def test_process_package_detection(self):
        """Test package detection processing."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Porch",
            "zone_id": "zone_porch",
            "entity_id": "camera.porch",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Process package detection
        alert = engine.process_package_detection(camera_id)
        
        assert alert is not None
        assert alert.alert_type == AlertType.PACKAGE_DETECTED
        assert alert.severity == AlertSeverity.INFO
    
    def test_acknowledge_alert(self):
        """Test alert acknowledgment."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        alert = engine.process_motion_event(camera_id, motion_detected=True)
        
        # Acknowledge
        result = engine.acknowledge_alert(alert.alert_id)
        assert result is True
        
        # Verify acknowledged
        assert engine._alerts[alert.alert_id].acknowledged is True
        assert engine._alerts[alert.alert_id].acknowledged_at is not None
    
    def test_resolve_alert(self):
        """Test alert resolution."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        alert = engine.process_motion_event(camera_id, motion_detected=True)
        
        # Resolve
        result = engine.resolve_alert(alert.alert_id)
        assert result is True
        
        # Verify resolved
        assert engine._alerts[alert.alert_id].resolved is True
        assert engine._alerts[alert.alert_id].resolved_at is not None
    
    def test_get_alerts_unresolved_only(self):
        """Test getting unresolved alerts only."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Create multiple alerts
        engine.process_motion_event(camera_id, motion_detected=True)
        engine.process_motion_event(camera_id, motion_detected=True)
        
        # Resolve one
        alerts = engine.get_alerts(unresolved_only=True)
        engine.resolve_alert(alerts[0]["alert_id"])
        
        # Get unresolved only
        unresolved = engine.get_alerts(unresolved_only=True)
        assert len(unresolved) == 1
    
    def test_get_alerts_filtered_by_zone(self):
        """Test getting alerts filtered by zone."""
        engine = CameraSecurityEngine()
        
        # Register cameras in different zones
        engine.register_camera({
            "name": "Cam A",
            "zone_id": "zone_a",
            "entity_id": "camera.a",
        })
        
        engine.register_camera({
            "name": "Cam B",
            "zone_id": "zone_b",
            "entity_id": "camera.b",
        })
        
        # Create alerts
        for camera_id in engine._cameras.keys():
            engine.process_motion_event(camera_id, motion_detected=True)
        
        # Filter by zone_a
        alerts_a = engine.get_alerts(zone_id="zone_a")
        assert all(a["zone_id"] == "zone_a" for a in alerts_a)
    
    def test_get_snapshots(self):
        """Test getting snapshots."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Create snapshots via motion events
        engine.process_motion_event(camera_id, motion_detected=True)
        engine.process_motion_event(camera_id, motion_detected=True)
        
        snapshots = engine.get_snapshots(limit=10)
        assert len(snapshots) >= 1
        assert all(s["camera_id"] == camera_id for s in snapshots)
    
    def test_get_cameras_filtered_by_zone(self):
        """Test getting cameras filtered by zone."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Zone A Cam",
            "zone_id": "zone_a",
            "entity_id": "camera.a",
        })
        
        engine.register_camera({
            "name": "Zone B Cam",
            "zone_id": "zone_b",
            "entity_id": "camera.b",
        })
        
        # Filter by zone_a
        cameras_a = engine.get_cameras(zone_id="zone_a")
        assert len(cameras_a) == 1
        assert cameras_a[0]["zone_id"] == "zone_a"
    
    def test_zone_security_level_elevation(self):
        """Test zone security level elevation on motion."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Initial level should be MEDIUM
        initial_level = engine.get_zone_security_level("zone_test")
        assert initial_level == SecurityLevel.MEDIUM
        
        # Motion should elevate to HIGH
        engine.process_motion_event(camera_id, motion_detected=True)
        elevated_level = engine.get_zone_security_level("zone_test")
        assert elevated_level == SecurityLevel.HIGH
    
    def test_get_security_summary(self):
        """Test security summary generation."""
        engine = CameraSecurityEngine()
        
        # Register cameras
        engine.register_camera({
            "name": "Cam 1",
            "zone_id": "zone_1",
            "entity_id": "camera.c1",
        })
        
        engine.register_camera({
            "name": "Cam 2",
            "zone_id": "zone_2",
            "entity_id": "camera.c2",
        })
        
        # Create alerts
        for camera_id in engine._cameras.keys():
            engine.process_motion_event(camera_id, motion_detected=True)
        
        summary = engine.get_security_summary()
        
        assert summary["total_cameras"] == 2
        assert summary["active_cameras"] == 2
        assert summary["total_alerts"] >= 1
        assert summary["unresolved_alerts"] >= 1
        assert summary["zones_monitored"] == 2
    
    def test_disabled_camera_no_alerts(self):
        """Test that disabled cameras don't generate alerts."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Disabled",
            "zone_id": "zone_test",
            "entity_id": "camera.disabled",
            "enabled": False,
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Motion on disabled camera should not create alert
        alert = engine.process_motion_event(camera_id, motion_detected=True)
        assert alert is None
    
    def test_alert_sorted_by_created_at(self):
        """Test that alerts are sorted by created_at (newest first)."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Create multiple alerts
        for i in range(5):
            engine.process_motion_event(camera_id, motion_detected=True)
        
        alerts = engine.get_alerts(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(alerts) - 1):
            assert alerts[i]["created_at"] >= alerts[i + 1]["created_at"]
    
    def test_snapshot_sorted_by_created_at(self):
        """Test that snapshots are sorted by created_at (newest first)."""
        engine = CameraSecurityEngine()
        
        engine.register_camera({
            "name": "Test",
            "zone_id": "zone_test",
            "entity_id": "camera.test",
        })
        
        camera_id = list(engine._cameras.keys())[0]
        
        # Create multiple snapshots
        for i in range(5):
            engine.process_motion_event(camera_id, motion_detected=True)
        
        snapshots = engine.get_snapshots(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(snapshots) - 1):
            assert snapshots[i]["created_at"] >= snapshots[i + 1]["created_at"]
    
    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = SecurityAlert(
            alert_id="alert_test",
            alert_type=AlertType.MOTION_DETECTED,
            severity=AlertSeverity.WARNING,
            camera_id="cam_test",
            zone_id="zone_test",
            description="Test alert",
        )
        
        d = alert.to_dict()
        
        assert d["alert_id"] == "alert_test"
        assert d["alert_type"] == "motion_detected"
        assert d["severity"] == "warning"
        assert d["zone_id"] == "zone_test"
        assert d["acknowledged"] is False
        assert d["resolved"] is False
    
    def test_snapshot_to_dict(self):
        """Test snapshot serialization."""
        snapshot = SecuritySnapshot(
            snapshot_id="snapshot_test",
            camera_id="cam_test",
            zone_id="zone_test",
            image_url="/api/camera/test/1",
            motion_detected=True,
        )
        
        d = snapshot.to_dict()
        
        assert d["snapshot_id"] == "snapshot_test"
        assert d["camera_id"] == "cam_test"
        assert d["image_url"] == "/api/camera/test/1"
        assert d["motion_detected"] is True
    
    def test_camera_to_dict(self):
        """Test camera config serialization."""
        from copilot_core.camera.security_engine import CameraConfig
        
        camera = CameraConfig(
            camera_id="cam_test",
            name="Test Camera",
            zone_id="zone_test",
            entity_id="camera.test",
            enabled=True,
        )
        
        d = camera.to_dict()
        
        assert d["camera_id"] == "cam_test"
        assert d["name"] == "Test Camera"
        assert d["zone_id"] == "zone_test"
        assert d["entity_id"] == "camera.test"
        assert d["enabled"] is True
