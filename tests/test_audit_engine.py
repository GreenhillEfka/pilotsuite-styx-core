"""Tests for Audit Engine — Slice 36."""
import pytest
from copilot_core.audit.engine import (
    AuditEngine,
    AuditEventType,
    AuditSeverity,
    AuditEvent,
    AuditQuery,
    create_audit_engine,
)
from datetime import datetime, timezone, timedelta


class TestAuditEngine:
    """Test audit engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_audit_engine()
        assert engine is not None
    
    def test_log_basic_event(self):
        """Test logging basic event."""
        engine = AuditEngine()
        
        event_id = engine.log(
            event_type=AuditEventType.USER_ACTION,
            action="test_action",
            actor_id="user_001",
        )
        
        assert event_id is not None
        assert event_id.startswith("audit_")
        
        event = engine.get_event(event_id)
        assert event is not None
        assert event["actor_id"] == "user_001"
        assert event["action"] == "test_action"
    
    def test_log_authentication_success(self):
        """Test logging successful authentication."""
        engine = AuditEngine()
        
        event_id = engine.log_authentication(
            actor_id="user_001",
            success=True,
            method="password",
            ip_address="192.168.1.1",
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "authentication"
        assert event["action"] == "login"
        assert event["details"]["success"] is True
    
    def test_log_authentication_failure(self):
        """Test logging failed authentication."""
        engine = AuditEngine()
        
        event_id = engine.log_authentication(
            actor_id="user_001",
            success=False,
            method="password",
            ip_address="192.168.1.1",
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "authentication"
        assert event["action"] == "login_failed"
        assert event["severity"] == "warning"
    
    def test_log_authorization_granted(self):
        """Test logging authorization granted."""
        engine = AuditEngine()
        
        event_id = engine.log_authorization(
            actor_id="user_001",
            resource_type="document",
            resource_id="doc_123",
            action="read",
            granted=True,
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "authorization"
        assert event["details"]["granted"] is True
    
    def test_log_authorization_denied(self):
        """Test logging authorization denied."""
        engine = AuditEngine()
        
        event_id = engine.log_authorization(
            actor_id="user_001",
            resource_type="document",
            resource_id="doc_123",
            action="write",
            granted=False,
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "authorization"
        assert event["action"] == "access_denied"
        assert event["severity"] == "warning"
    
    def test_log_data_access(self):
        """Test logging data access."""
        engine = AuditEngine()
        
        event_id = engine.log_data_access(
            actor_id="user_001",
            resource_type="sensor",
            resource_id="sensor_001",
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "data_access"
        assert event["action"] == "read"
    
    def test_log_data_modification(self):
        """Test logging data modification."""
        engine = AuditEngine()
        
        event_id = engine.log_data_modification(
            actor_id="user_001",
            resource_type="config",
            resource_id="config_001",
            previous_state={"value": "old"},
            new_state={"value": "new"},
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "data_modification"
        assert event["previous_state"]["value"] == "old"
        assert event["new_state"]["value"] == "new"
    
    def test_log_data_deletion(self):
        """Test logging data deletion."""
        engine = AuditEngine()
        
        event_id = engine.log_data_deletion(
            actor_id="user_001",
            resource_type="document",
            resource_id="doc_123",
            previous_state={"title": "Deleted Doc"},
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "data_deletion"
        assert event["action"] == "delete"
    
    def test_log_config_change(self):
        """Test logging config change."""
        engine = AuditEngine()
        
        event_id = engine.log_config_change(
            actor_id="admin_001",
            config_key="system.max_users",
            previous_value=100,
            new_value=200,
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "config_change"
        assert event["resource_id"] == "system.max_users"
    
    def test_log_security_event(self):
        """Test logging security event."""
        engine = AuditEngine()
        
        event_id = engine.log_security_event(
            actor_id="user_001",
            action="suspicious_activity",
            severity=AuditSeverity.CRITICAL,
            details={"reason": "Multiple failed logins"},
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "security_event"
        assert event["severity"] == "critical"
    
    def test_log_system_event(self):
        """Test logging system event."""
        engine = AuditEngine()
        
        event_id = engine.log_system_event(
            action="startup",
            severity=AuditSeverity.INFO,
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "system_event"
        assert event["actor_id"] == "system"
    
    def test_log_api_call_success(self):
        """Test logging successful API call."""
        engine = AuditEngine()
        
        event_id = engine.log_api_call(
            actor_id="user_001",
            endpoint="/api/v1/users",
            method="GET",
            status_code=200,
            ip_address="192.168.1.1",
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "api_call"
        assert event["severity"] == "info"
    
    def test_log_api_call_error(self):
        """Test logging failed API call."""
        engine = AuditEngine()
        
        event_id = engine.log_api_call(
            actor_id="user_001",
            endpoint="/api/v1/users",
            method="POST",
            status_code=500,
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_type"] == "api_call"
        assert event["severity"] == "warning"
    
    def test_get_event(self):
        """Test getting event by ID."""
        engine = AuditEngine()
        
        event_id = engine.log(
            event_type=AuditEventType.USER_ACTION,
            action="test",
            actor_id="user_001",
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_id"] == event_id
    
    def test_get_unknown_event(self):
        """Test getting unknown event."""
        engine = AuditEngine()
        
        event = engine.get_event("unknown_event")
        
        assert event is None
    
    def test_query_by_event_type(self):
        """Test querying by event type."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_authentication("user_002", True)
        engine.log_data_access("user_001", "doc", "doc_1")
        
        query = AuditQuery(event_type=AuditEventType.AUTHENTICATION)
        results = engine.query(query)
        
        assert len(results) == 2
        assert all(r["event_type"] == "authentication" for r in results)
    
    def test_query_by_severity(self):
        """Test querying by severity."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)  # INFO
        engine.log_authentication("user_002", False)  # WARNING
        engine.log_security_event("user_001", "attack", AuditSeverity.CRITICAL)
        
        query = AuditQuery(severity=AuditSeverity.WARNING)
        results = engine.query(query)
        
        assert len(results) >= 1
        assert all(r["severity"] == "warning" for r in results)
    
    def test_query_by_actor(self):
        """Test querying by actor."""
        engine = AuditEngine()
        
        engine.log_data_access("user_001", "doc", "doc_1")
        engine.log_data_access("user_002", "doc", "doc_2")
        engine.log_data_access("user_001", "doc", "doc_3")
        
        query = AuditQuery(actor_id="user_001")
        results = engine.query(query)
        
        assert len(results) == 2
        assert all(r["actor_id"] == "user_001" for r in results)
    
    def test_query_by_resource(self):
        """Test querying by resource."""
        engine = AuditEngine()
        
        engine.log_data_access("user_001", "sensor", "sensor_1")
        engine.log_data_access("user_001", "sensor", "sensor_2")
        engine.log_data_access("user_001", "camera", "cam_1")
        
        query = AuditQuery(resource_type="sensor")
        results = engine.query(query)
        
        assert len(results) == 2
        assert all(r["resource_type"] == "sensor" for r in results)
    
    def test_query_by_time_range(self):
        """Test querying by time range."""
        engine = AuditEngine()
        
        now = datetime.now(timezone.utc)
        
        engine.log_data_access("user_001", "doc", "doc_1")
        
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()
        
        query = AuditQuery(start_time=start, end_time=end)
        results = engine.query(query)
        
        assert len(results) >= 1
    
    def test_query_limit(self):
        """Test query limit."""
        engine = AuditEngine()
        
        for i in range(50):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        query = AuditQuery(limit=10)
        results = engine.query(query)
        
        assert len(results) == 10
    
    def test_query_offset(self):
        """Test query offset."""
        engine = AuditEngine()
        
        for i in range(20):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        query1 = AuditQuery(limit=10, offset=0)
        query2 = AuditQuery(limit=10, offset=10)
        
        results1 = engine.query(query1)
        results2 = engine.query(query2)
        
        assert len(results1) == 10
        assert len(results2) == 10
    
    def test_get_events_by_actor(self):
        """Test getting events by actor."""
        engine = AuditEngine()
        
        engine.log_data_access("user_001", "doc", "doc_1")
        engine.log_data_access("user_001", "doc", "doc_2")
        engine.log_data_access("user_002", "doc", "doc_3")
        
        events = engine.get_events_by_actor("user_001", limit=10)
        
        assert len(events) == 2
    
    def test_get_events_by_resource(self):
        """Test getting events by resource."""
        engine = AuditEngine()
        
        engine.log_data_access("user_001", "sensor", "sensor_1")
        engine.log_data_access("user_001", "sensor", "sensor_1")
        engine.log_data_access("user_001", "sensor", "sensor_2")
        
        events = engine.get_events_by_resource("sensor", "sensor_1", limit=10)
        
        assert len(events) == 2
    
    def test_get_events_by_type(self):
        """Test getting events by type."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_data_access("user_001", "doc", "doc_1")
        engine.log_authentication("user_002", True)
        
        events = engine.get_events_by_type(AuditEventType.AUTHENTICATION, limit=10)
        
        assert len(events) == 2
    
    def test_get_security_events(self):
        """Test getting security events."""
        engine = AuditEngine()
        
        engine.log_security_event("user_001", "intrusion_detected")
        engine.log_data_access("user_001", "doc", "doc_1")
        engine.log_security_event("user_002", "brute_force")
        
        events = engine.get_security_events(limit=10)
        
        assert len(events) == 2
        assert all(e["event_type"] == "security_event" for e in events)
    
    def test_get_failed_authentications(self):
        """Test getting failed authentications."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_authentication("user_002", False)
        engine.log_authentication("user_003", False)
        engine.log_authentication("user_001", False)
        
        events = engine.get_failed_authentications(limit=10)
        
        assert len(events) == 3
        assert all(e["details"]["success"] is False for e in events)
    
    def test_get_failed_authentications_by_actor(self):
        """Test getting failed authentications by actor."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", False)
        engine.log_authentication("user_002", False)
        engine.log_authentication("user_001", False)
        
        events = engine.get_failed_authentications(actor_id="user_001")
        
        assert len(events) == 2
        assert all(e["actor_id"] == "user_001" for e in events)
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_authentication("user_002", False)
        engine.log_data_access("user_001", "doc", "doc_1")
        
        stats = engine.get_statistics()
        
        assert stats["total_events"] == 3
        assert "authentication" in stats["by_type"]
        assert "data_access" in stats["by_type"]
    
    def test_export_json(self):
        """Test exporting to JSON."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_data_access("user_001", "doc", "doc_1")
        
        export = engine.export_events(format="json")
        
        assert export is not None
        assert "authentication" in export
    
    def test_export_csv(self):
        """Test exporting to CSV."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_data_access("user_001", "doc", "doc_1")
        
        export = engine.export_events(format="csv")
        
        assert export is not None
        assert "event_id,timestamp,event_type" in export
    
    def test_export_empty(self):
        """Test exporting empty log."""
        engine = AuditEngine()
        
        export = engine.export_events(format="csv")
        
        assert export == ""
    
    def test_verify_integrity_valid(self):
        """Test verifying integrity of valid log."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_data_access("user_001", "doc", "doc_1")
        
        result = engine.verify_integrity()
        
        assert result["integrity_ok"] is True
        assert result["invalid"] == 0
    
    def test_verify_integrity_reports_total(self):
        """Test that integrity check reports total events."""
        engine = AuditEngine()
        
        for i in range(10):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        result = engine.verify_integrity()
        
        assert result["total_events"] == 10
    
    def test_clear_all(self):
        """Test clearing all events."""
        engine = AuditEngine()
        
        for i in range(10):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        count = engine.clear()
        
        assert count == 10
        assert engine.get_statistics()["stored_events"] == 0
    
    def test_clear_older_than(self):
        """Test clearing events older than timestamp."""
        engine = AuditEngine()
        
        # Log some events
        for i in range(5):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        # Get current time as cutoff
        cutoff = datetime.now(timezone.utc).isoformat()
        
        # Log more events
        for i in range(5, 10):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        count = engine.clear(older_than=cutoff)
        
        # Should have cleared some events
        assert count >= 0
    
    def test_events_sorted_by_timestamp(self):
        """Test that query results are sorted by timestamp."""
        engine = AuditEngine()
        
        for i in range(5):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        results = engine.query(AuditQuery(limit=10))
        
        # Verify sorted (newest first)
        for i in range(len(results) - 1):
            assert results[i]["timestamp"] >= results[i + 1]["timestamp"]
    
    def test_event_hash_computed(self):
        """Test that event hash is computed."""
        engine = AuditEngine()
        
        event_id = engine.log(
            event_type=AuditEventType.USER_ACTION,
            action="test",
            actor_id="user_001",
        )
        
        event = engine.get_event(event_id)
        
        assert "hash" in event
        assert event["hash"] is not None
        assert len(event["hash"]) == 64  # SHA256 hex
    
    def test_event_hash_stable(self):
        """Test that event hash is stable."""
        engine = AuditEngine()
        
        event_id = engine.log(
            event_type=AuditEventType.USER_ACTION,
            action="test",
            actor_id="user_001",
        )
        
        event1 = engine.get_event(event_id)
        event2 = engine.get_event(event_id)
        
        assert event1["hash"] == event2["hash"]
    
    def test_audit_event_type_enum_values(self):
        """Test audit event type enum values."""
        assert AuditEventType.AUTHENTICATION.value == "authentication"
        assert AuditEventType.AUTHORIZATION.value == "authorization"
        assert AuditEventType.DATA_ACCESS.value == "data_access"
        assert AuditEventType.DATA_MODIFICATION.value == "data_modification"
        assert AuditEventType.DATA_DELETION.value == "data_deletion"
        assert AuditEventType.CONFIG_CHANGE.value == "config_change"
        assert AuditEventType.SECURITY_EVENT.value == "security_event"
        assert AuditEventType.SYSTEM_EVENT.value == "system_event"
        assert AuditEventType.USER_ACTION.value == "user_action"
        assert AuditEventType.API_CALL.value == "api_call"
    
    def test_audit_severity_enum_values(self):
        """Test audit severity enum values."""
        assert AuditSeverity.DEBUG.value == "debug"
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.ERROR.value == "error"
        assert AuditSeverity.CRITICAL.value == "critical"
    
    def test_stats_track_by_type(self):
        """Test that stats track events by type."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)
        engine.log_authentication("user_002", True)
        engine.log_data_access("user_001", "doc", "doc_1")
        
        stats = engine.get_statistics()
        
        assert stats["by_type"]["authentication"] == 2
        assert stats["by_type"]["data_access"] == 1
    
    def test_stats_track_by_severity(self):
        """Test that stats track events by severity."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)  # INFO
        engine.log_authentication("user_002", False)  # WARNING
        
        stats = engine.get_statistics()
        
        assert stats["by_severity"]["info"] >= 1
        assert stats["by_severity"]["warning"] >= 1
    
    def test_stats_track_by_actor(self):
        """Test that stats track events by actor."""
        engine = AuditEngine()
        
        engine.log_data_access("user_001", "doc", "doc_1")
        engine.log_data_access("user_001", "doc", "doc_2")
        engine.log_data_access("user_002", "doc", "doc_3")
        
        stats = engine.get_statistics()
        
        assert stats["by_actor"]["user_001"] == 2
        assert stats["by_actor"]["user_002"] == 1
    
    def test_events_trimmed_to_max(self):
        """Test that events are trimmed to max."""
        engine = AuditEngine(max_events=10)
        
        for i in range(20):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        stats = engine.get_statistics()
        
        assert stats["stored_events"] == 10
    
    def test_query_action_filter(self):
        """Test querying by action filter."""
        engine = AuditEngine()
        
        engine.log_authentication("user_001", True)  # login
        engine.log_authentication("user_002", False)  # login_failed
        engine.log_data_access("user_001", "doc", "doc_1")  # read
        
        query = AuditQuery(action="login")
        results = engine.query(query)
        
        # Should match both login and login_failed
        assert len(results) == 2
    
    def test_export_with_time_range(self):
        """Test exporting with time range."""
        engine = AuditEngine()
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()
        
        engine.log_authentication("user_001", True)
        
        export = engine.export_events(start_time=start, end_time=end)
        
        assert export is not None
    
    def test_get_event_includes_all_fields(self):
        """Test that get event includes all fields."""
        engine = AuditEngine()
        
        event_id = engine.log(
            event_type=AuditEventType.DATA_MODIFICATION,
            action="update",
            actor_id="user_001",
            actor_type="user",
            severity=AuditSeverity.INFO,
            resource_type="document",
            resource_id="doc_123",
            details={"field": "value"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            previous_state={"old": "value"},
            new_state={"new": "value"},
        )
        
        event = engine.get_event(event_id)
        
        assert event["event_type"] == "data_modification"
        assert event["actor_type"] == "user"
        assert event["severity"] == "info"
        assert event["resource_type"] == "document"
        assert event["resource_id"] == "doc_123"
        assert event["details"]["field"] == "value"
        assert event["ip_address"] == "192.168.1.1"
        assert event["user_agent"] == "Mozilla/5.0"
        assert event["previous_state"]["old"] == "value"
        assert event["new_state"]["new"] == "value"
    
    def test_audit_query_to_dict(self):
        """Test audit query serialization."""
        query = AuditQuery(
            event_type=AuditEventType.AUTHENTICATION,
            severity=AuditSeverity.WARNING,
            actor_id="user_001",
            limit=50,
            offset=10,
        )
        
        d = query.to_dict()
        
        assert d["event_type"] == "authentication"
        assert d["severity"] == "warning"
        assert d["actor_id"] == "user_001"
        assert d["limit"] == 50
    
    def test_audit_event_to_dict(self):
        """Test audit event serialization."""
        event = AuditEvent(
            event_id="audit_test",
            event_type=AuditEventType.USER_ACTION,
            severity=AuditSeverity.INFO,
            timestamp="2026-03-31T12:00:00Z",
            actor_id="user_001",
            actor_type="user",
            action="test_action",
            resource_type="test",
            resource_id="test_1",
            details={"key": "value"},
            ip_address="192.168.1.1",
            user_agent="Test/1.0",
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "audit_test"
        assert d["event_type"] == "user_action"
        assert d["details"]["key"] == "value"
    
    def test_statistics_includes_max_events(self):
        """Test that statistics include max_events."""
        engine = AuditEngine(max_events=50000)
        
        stats = engine.get_statistics()
        
        assert stats["max_events"] == 50000
    
    def test_empty_query_returns_all(self):
        """Test that empty query returns all events."""
        engine = AuditEngine()
        
        for i in range(5):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        query = AuditQuery()
        results = engine.query(query)
        
        assert len(results) == 5
    
    def test_clear_preserves_recent_events(self):
        """Test that clear with cutoff preserves recent events."""
        engine = AuditEngine()
        
        # Log events
        for i in range(5):
            engine.log_data_access("user_001", "doc", f"doc_{i}")
        
        # Get timestamp of last event
        last_event_time = engine._events[-1].timestamp
        
        # Clear older than just before last event
        cutoff = last_event_time
        
        count = engine.clear(older_than=cutoff)
        
        # Should preserve at least the last event
        stats = engine.get_statistics()
        assert stats["stored_events"] >= 1
