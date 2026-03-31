"""Tests for HA Connection Read Model — Core-side HA connection/preparation layer."""

from __future__ import annotations

from pathlib import Path
import sys
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from copilot_core.core.ha_connection_read_model import (
    HAConnectionSnapshotV1,
    HAConnectionReadModel,
    ConnectionDiagnosticsV1,
    EventForwardingStateV1,
    WebhookDiagnosticsV1,
    SupervisorStateV1,
    build_ha_connection_read_model,
    get_ha_connection_read_model,
    update_ha_connection,
    get_ha_connection_state,
    reset_ha_connection_state,
)


class TestConnectionDiagnosticsV1:
    """Tests for ConnectionDiagnosticsV1 dataclass."""

    def test_create_connection_diagnostics(self) -> None:
        """Test creating connection diagnostics."""
        diag = ConnectionDiagnosticsV1(
            reachable=True,
            response_time_ms=45.2,
            success_count=100,
            error_count=2,
        )
        
        assert diag.reachable is True
        assert diag.response_time_ms == 45.2
        assert diag.success_count == 100
        assert diag.error_count == 2

    def test_connection_diagnostics_to_dict(self) -> None:
        """Test diagnostics serialization."""
        diag = ConnectionDiagnosticsV1(
            reachable=False,
            response_time_ms=0.0,
            last_error="Connection timeout",
        )
        
        data = diag.to_dict()
        
        assert data["reachable"] is False
        assert data["response_time_ms"] == 0.0
        assert data["last_error"] == "Connection timeout"


class TestEventForwardingStateV1:
    """Tests for EventForwardingStateV1 dataclass."""

    def test_create_forwarding_state(self) -> None:
        """Test creating event forwarding state."""
        fwd = EventForwardingStateV1(
            enabled=True,
            forwarded_domains=["light", "sensor", "binary_sensor"],
            events_forwarded_count=500,
        )
        
        assert fwd.enabled is True
        assert len(fwd.forwarded_domains) == 3
        assert fwd.events_forwarded_count == 500

    def test_forwarding_state_to_dict(self) -> None:
        """Test forwarding state serialization."""
        fwd = EventForwardingStateV1(
            forwarded_domains=["climate", "media_player"],
            domain_counts={"climate": 100, "media_player": 50},
        )
        
        data = fwd.to_dict()
        
        assert data["forwarded_domains"] == ["climate", "media_player"]
        assert data["domain_counts"]["climate"] == 100


class TestWebhookDiagnosticsV1:
    """Tests for WebhookDiagnosticsV1 dataclass."""

    def test_webhook_diagnostics(self) -> None:
        """Test webhook diagnostics structure."""
        wh = WebhookDiagnosticsV1(
            push_count=200,
            push_errors=3,
            received_count=150,
            received_by_type={"state_changed": 100, "event": 50},
        )
        
        data = wh.to_dict()
        
        assert data["outbound"]["push_count"] == 200
        assert data["outbound"]["push_errors"] == 3
        assert data["inbound"]["received_count"] == 150
        assert data["inbound"]["received_by_type"]["state_changed"] == 100


class TestHAConnectionSnapshotV1:
    """Tests for HAConnectionSnapshotV1 dataclass."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_ha_connection_state()

    def test_create_snapshot(self) -> None:
        """Test creating HA connection snapshot."""
        snapshot = HAConnectionSnapshotV1()
        
        assert snapshot.module_id == "homeassistant"
        assert snapshot.module_name_de == "Home Assistant Verbindung"
        assert snapshot.module_icon == "mdi:home-assistant"
        assert snapshot.pipeline_health == "ok"
        assert snapshot.revision == 0

    def test_snapshot_touch(self) -> None:
        """Test revision increment on touch."""
        snapshot = HAConnectionSnapshotV1()
        initial_revision = snapshot.revision
        
        snapshot.touch()
        
        assert snapshot.revision == initial_revision + 1

    def test_compute_pipeline_health_reachable(self) -> None:
        """Test pipeline health computation when reachable."""
        snapshot = HAConnectionSnapshotV1()
        snapshot.connection.reachable = True
        snapshot.connection.success_count = 100
        snapshot.connection.error_count = 2
        snapshot.connection.response_time_ms = 50.0
        
        snapshot.compute_pipeline_health()
        
        assert snapshot.pipeline_health == "ok"
        assert snapshot.pipeline_color == "#34d399"  # green

    def test_compute_pipeline_health_unreachable(self) -> None:
        """Test pipeline health when unreachable."""
        snapshot = HAConnectionSnapshotV1()
        snapshot.connection.reachable = False
        
        snapshot.compute_pipeline_health()
        
        assert snapshot.pipeline_health == "error"
        assert snapshot.pipeline_color == "#ef4444"  # red

    def test_compute_pipeline_health_degraded_error_rate(self) -> None:
        """Test pipeline health with high error rate."""
        snapshot = HAConnectionSnapshotV1()
        snapshot.connection.reachable = True
        snapshot.connection.success_count = 10
        snapshot.connection.error_count = 5  # 33% error rate
        
        snapshot.compute_pipeline_health()
        
        assert snapshot.pipeline_health == "degraded"
        assert snapshot.pipeline_color == "#f59e0b"  # amber

    def test_compute_pipeline_health_slow_response(self) -> None:
        """Test pipeline health with slow response time."""
        snapshot = HAConnectionSnapshotV1()
        snapshot.connection.reachable = True
        snapshot.connection.success_count = 100
        snapshot.connection.error_count = 0
        snapshot.connection.response_time_ms = 6000.0  # 6 seconds
        
        snapshot.compute_pipeline_health()
        
        assert snapshot.pipeline_health == "degraded"

    def test_snapshot_to_dict(self) -> None:
        """Test full snapshot serialization."""
        snapshot = HAConnectionSnapshotV1()
        snapshot.connection.reachable = True
        snapshot.connection.response_time_ms = 35.5
        snapshot.event_forwarding.forwarded_domains = ["light", "sensor"]
        snapshot.integration_entity_count = 150
        
        data = snapshot.to_dict()
        
        assert data["module_id"] == "homeassistant"
        assert data["connection"]["reachable"] is True
        assert data["connection"]["response_time_ms"] == 35.5
        assert data["event_forwarding"]["forwarded_domains"] == ["light", "sensor"]
        assert data["integration_entity_count"] == 150


class TestHAConnectionReadModel:
    """Tests for HAConnectionReadModel."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_ha_connection_state()

    def test_empty_read_model(self) -> None:
        """Test read model with no data."""
        model = build_ha_connection_read_model()
        
        assert model.generated_at is not None
        assert model.connection.module_id == "homeassistant"
        assert model.summary["reachable"] is False

    def test_read_model_to_dict(self) -> None:
        """Test read model serialization."""
        model = build_ha_connection_read_model()
        data = model.to_dict()
        
        assert "generated_at" in data
        assert "connection" in data
        assert "summary" in data
        assert "module_id" in data["connection"]


class TestHAConnectionAPI:
    """Tests for HA connection update/query API."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_ha_connection_state()

    def test_update_and_get_connection_state(self) -> None:
        """Test updating and retrieving connection state."""
        update_ha_connection(
            reachable=True,
            response_time_ms=42.5,
        )
        
        state = get_ha_connection_state()
        
        assert state is not None
        assert state["connection"]["reachable"] is True
        assert state["connection"]["response_time_ms"] == 42.5

    def test_update_connection_with_error(self) -> None:
        """Test updating connection with error."""
        update_ha_connection(
            reachable=False,
            response_time_ms=0.0,
            error_message="Connection timeout after 10s",
        )
        
        state = get_ha_connection_state()
        
        assert state is not None
        assert state["connection"]["reachable"] is False
        assert state["connection"]["last_error"] == "Connection timeout after 10s"
        assert state["pipeline_health"] == "error"


class TestHAConnectionReadModelIntegration:
    """Integration tests with mock HA module engine."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_ha_connection_state()

    def test_build_with_mock_engine(self) -> None:
        """Test building read model with mock HA module engine."""
        class MockConnection:
            reachable = True
            response_time_ms = 35.0
            success_count = 50
            error_count = 1
            last_successful_call = datetime(2026, 3, 31, 10, 0, 0, tzinfo=timezone.utc)
            last_failed_call = None
        
        class MockEventForwarding:
            forwarded_domains = ["light", "sensor", "binary_sensor", "climate"]
            events_forwarded_count = 250
            domain_counts = {"light": 100, "sensor": 80, "binary_sensor": 50, "climate": 20}
            last_event_at = datetime(2026, 3, 31, 10, 5, 0, tzinfo=timezone.utc)
        
        class MockWebhook:
            push_count = 30
            push_errors = 0
            last_error_message = ""
            last_push = datetime(2026, 3, 31, 9, 0, 0, tzinfo=timezone.utc)
        
        class MockSupervisor:
            reachable = True
            token_valid = True
            last_check = datetime(2026, 3, 31, 10, 0, 0, tzinfo=timezone.utc)
        
        class MockEngine:
            def __init__(self):
                self._connection = MockConnection()
                self._event_forwarding = MockEventForwarding()
                self._webhook = MockWebhook()
                self._supervisor = MockSupervisor()
                self._integration_entity_count = 120
                self._module_count = 8
                self._active_dashboard_views = ["zone_overview", "module_health"]
                self._connected_at = 1711879200.0  # Some monotonic timestamp
                self._last_error = None
                self._event_timestamps = [1711879200.0, 1711879260.0, 1711879320.0]
                self._config = {"enabled": True}
                self._last_webhook_received_at = None
                self._webhook_received_count = 0
                self._webhook_event_types = {}
        
        model = build_ha_connection_read_model(ha_module_engine=MockEngine())
        
        # Connection checks
        assert model.connection.connection.reachable is True
        assert model.connection.connection.response_time_ms == 35.0
        assert model.connection.connection.success_count == 50
        
        # Event forwarding checks
        assert len(model.connection.event_forwarding.forwarded_domains) == 4
        assert model.connection.event_forwarding.events_forwarded_count == 250
        
        # Supervisor checks
        assert model.connection.supervisor.reachable is True
        assert model.connection.supervisor.token_valid is True
        
        # Metadata checks
        assert model.connection.integration_entity_count == 120
        assert model.connection.module_count == 8
        
        # Pipeline health should be ok
        assert model.connection.pipeline_health == "ok"

    def test_build_with_unreachable_engine(self) -> None:
        """Test building read model when HA is unreachable."""
        class MockConnection:
            reachable = False
            response_time_ms = 0.0
            success_count = 10
            error_count = 5
            last_successful_call = None
            last_failed_call = datetime(2026, 3, 31, 10, 0, 0, tzinfo=timezone.utc)
        
        class MockEngine:
            def __init__(self):
                self._connection = MockConnection()
                self._event_forwarding = type('obj', (object,), {
                    "forwarded_domains": [],
                    "events_forwarded_count": 0,
                    "domain_counts": {},
                    "last_event_at": None,
                })()
                self._webhook = type('obj', (object,), {
                    "push_count": 0,
                    "push_errors": 0,
                    "last_error_message": "",
                    "last_push": None,
                })()
                self._supervisor = type('obj', (object,), {
                    "reachable": False,
                    "token_valid": False,
                    "last_check": None,
                })()
                self._integration_entity_count = 0
                self._module_count = 0
                self._active_dashboard_views = []
                self._connected_at = None
                self._last_error = "HA unreachable"
                self._event_timestamps = []
                self._config = {"enabled": True}
                self._last_webhook_received_at = None
                self._webhook_received_count = 0
                self._webhook_event_types = {}
        
        model = build_ha_connection_read_model(ha_module_engine=MockEngine())
        
        assert model.connection.connection.reachable is False
        assert model.connection.pipeline_health == "error"
        assert model.connection.connection.last_error == "HA unreachable"
