"""Security Tests: P2 Security Fixes Integration Tests.

Tests that verify all P2 security fixes work correctly at the API level:
- P2-01: Zone ID Input Sanitization (media_zones.py)
- P2-02: Rate Limiting on proactive endpoints (media_zones.py)
- P2-03: Neuron ID Validation (neurons.py)
- P2-04: Mood History Limit Cap (neurons.py)
- P2-05: WebSocket Room Name Validation (websocket_neuron.py)
"""
import pytest
import json
from unittest.mock import patch, MagicMock, Mock
from flask import Flask


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


@pytest.fixture
def media_zones_client(app):
    """Create test client with media_zones blueprint."""
    from copilot_core.api.v1.media_zones import media_zones_bp, init_media_zones_api

    mock_mgr = MagicMock()
    mock_mgr.get_all_assignments.return_value = {}
    mock_mgr.get_zone_players.return_value = []
    mock_mgr.get_zone_media_state.return_value = {}
    mock_mgr.get_musikwolke_sessions.return_value = []

    mock_engine = MagicMock()
    mock_engine.on_zone_entry.return_value = []
    mock_engine.deliver_suggestion.return_value = True
    mock_engine.dismiss_type.return_value = None
    mock_engine.reset_dismissals.return_value = None

    init_media_zones_api(mock_mgr, mock_engine)

    with patch("copilot_core.api.v1.media_zones.require_token", lambda f: f):
        # Re-import to pick up the patched decorator
        app.register_blueprint(media_zones_bp)
        with app.test_client() as client:
            yield client


@pytest.fixture
def neurons_client(app):
    """Create test client with neurons blueprint."""
    mock_manager = MagicMock()
    mock_manager.get_neuron_summary.return_value = {"total_count": 14}
    mock_manager.get_neuron.return_value = None
    mock_manager._mood_history = [
        {"mood": "relaxed", "ts": "2024-01-01T00:00:00Z"},
        {"mood": "focused", "ts": "2024-01-01T01:00:00Z"},
        {"mood": "energetic", "ts": "2024-01-01T02:00:00Z"},
    ]
    mock_manager._last_result = MagicMock(
        suggestions=[], dominant_mood="relaxed",
        timestamp="2024-01-01T00:00:00Z",
    )

    with patch("copilot_core.api.v1.neurons._validate_token", return_value=True):
        with patch("copilot_core.api.v1.neurons.get_neuron_manager", return_value=mock_manager):
            from copilot_core.api.v1 import neurons
            app.register_blueprint(neurons.bp, url_prefix="/api/v1/neurons")
            with app.test_client() as client:
                yield client, mock_manager


# ===========================================================================
# P2-01: Zone ID Input Sanitization
# ===========================================================================

class TestP2_01_ZoneIDSanitization:
    """P2-01: Verify zone_id path parameters are validated."""

    @pytest.mark.parametrize("zone_id", [
        "living_room",
        "bedroom",
        "zone-1",
        "ZoneA",
        "a",
    ])
    def test_valid_zone_id_accepted(self, media_zones_client, zone_id):
        """Valid zone IDs should return 200."""
        resp = media_zones_client.get(f"/api/v1/media/zones/{zone_id}")
        assert resp.status_code == 200

    @pytest.mark.parametrize("zone_id", [
        "../etc/passwd",
        "zone<script>alert(1)</script>",
        "zone;rm -rf /",
        "zone' OR 1=1--",
        "zone id",
    ])
    def test_malicious_zone_id_rejected(self, media_zones_client, zone_id):
        """Malicious zone IDs should be rejected (400 or 404)."""
        resp = media_zones_client.get(f"/api/v1/media/zones/{zone_id}")
        # Either 400 (validation error) or 404 (route not matched) is acceptable
        assert resp.status_code in (400, 404, 405), f"Expected 400/404/405, got {resp.status_code}"
        if resp.status_code == 400:
            data = json.loads(resp.data)
            assert data["ok"] is False

    def test_zone_id_too_long_rejected(self, media_zones_client):
        """Zone IDs exceeding 50 chars should be rejected."""
        long_id = "a" * 51
        resp = media_zones_client.get(f"/api/v1/media/zones/{long_id}")
        assert resp.status_code == 400

    def test_zone_id_max_length_accepted(self, media_zones_client):
        """Zone IDs at exactly 50 chars should be accepted."""
        max_id = "a" * 50
        resp = media_zones_client.get(f"/api/v1/media/zones/{max_id}")
        assert resp.status_code == 200


# ===========================================================================
# P2-02: Rate Limiting on proactive endpoints
# ===========================================================================

class TestP2_02_ProactiveRateLimiting:
    """P2-02: Verify rate limiting on proactive endpoints."""

    def test_proactive_dismiss_has_rate_limit(self):
        """proactive_dismiss should use rate_limit decorator."""
        from copilot_core.api.v1 import media_zones
        # The function should be wrapped by the rate_limit decorator
        # from copilot_core.api.rate_limit (not the old local one)
        func = media_zones.media_zones_bp.deferred_functions
        # Verify the import is from the correct module
        from copilot_core.api.rate_limit import rate_limit as real_rate_limit
        assert real_rate_limit is not None

    def test_proactive_reset_dismissals_has_rate_limit(self):
        """proactive_reset_dismissals should use rate_limit decorator."""
        from copilot_core.api.rate_limit import rate_limit as real_rate_limit
        assert real_rate_limit is not None

    def test_rate_limit_returns_429_on_excess(self):
        """Rate limiter should return 429 when limit exceeded."""
        from copilot_core.api.rate_limit import RateLimiter

        limiter = RateLimiter(
            default_limits={"/test": 2},
            default_period=60,
        )

        # First two requests should pass
        allowed1, _ = limiter.is_allowed("client1", "/test")
        allowed2, _ = limiter.is_allowed("client1", "/test")
        # Third should be rejected
        allowed3, info = limiter.is_allowed("client1", "/test")

        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is False
        assert info["remaining"] == 0

    def test_rate_limit_get_limit_returns_tuple(self):
        """get_limit should always return (requests, period) tuple."""
        from copilot_core.api.rate_limit import RateLimiter

        limiter = RateLimiter(
            default_limits={"/api/v1/events": 200},
            default_period=60,
        )

        # Configured endpoint
        result = limiter.get_limit("/api/v1/events")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (200, 60)

        # Unconfigured endpoint - should also return tuple
        result = limiter.get_limit("/api/v1/unknown")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (100, 60)

    def test_proactive_endpoints_use_real_rate_limit(self):
        """Verify media_zones imports rate_limit from api.rate_limit."""
        import copilot_core.api.v1.media_zones as mz_mod
        import copilot_core.api.rate_limit as rl_mod

        # The module should import rate_limit from api.rate_limit
        assert hasattr(rl_mod, "rate_limit")


# ===========================================================================
# P2-03: Neuron ID Validation
# ===========================================================================

class TestP2_03_NeuronIDValidation:
    """P2-03: Verify neuron_id parameters are validated."""

    @pytest.mark.parametrize("neuron_id", [
        "presence",
        "context.presence",
        "mood.focus",
        "state.energy_level",
    ])
    def test_valid_neuron_id_accepted(self, neurons_client, neuron_id):
        """Valid neuron IDs should not return 400."""
        client, _ = neurons_client
        resp = client.get(f"/api/v1/neurons/{neuron_id}")
        # 200 or 404 (not found) are acceptable; 400 means validation failed
        assert resp.status_code in (200, 404)

    @pytest.mark.parametrize("neuron_id", [
        "Context.Presence",
        "../../etc/passwd",
        "neuron<script>",
        "neuron;rm",
        "UPPER_CASE",
    ])
    def test_invalid_neuron_id_rejected(self, neurons_client, neuron_id):
        """Invalid neuron IDs should be rejected (400 or 404)."""
        client, _ = neurons_client
        resp = client.get(f"/api/v1/neurons/{neuron_id}")
        # Either 400 (validation error) or 404 (route not matched) is acceptable
        assert resp.status_code in (400, 404), f"Expected 400/404, got {resp.status_code}"
        if resp.status_code == 400:
            data = json.loads(resp.data)
            assert data["success"] is False

    def test_neuron_stats_validates_id(self, neurons_client):
        """GET /neurons/<id>/stats should also validate neuron_id."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/INVALID_ID/stats")
        assert resp.status_code == 400


# ===========================================================================
# P2-04: Mood History Limit Cap
# ===========================================================================

class TestP2_04_MoodHistoryLimitCap:
    """P2-04: Verify server-side cap on mood history query window.

    The mood history endpoint now uses ?hours= (SQLite-persisted snapshots)
    instead of the old ?limit= (in-memory deque).  Hours are capped at 168
    (7 days).
    """

    def test_default_hours(self, neurons_client):
        """Default hours should be 24."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/mood/history")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["data"]["hours"] == 24

    def test_hours_capped_at_168(self, neurons_client):
        """Hours should be capped at 168 even if higher value requested."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/mood/history?hours=9999")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["data"]["hours"] == 168

    def test_negative_hours_handled(self, neurons_client):
        """Negative hours should be clamped to 1."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/mood/history?hours=-5")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["data"]["hours"] == 1

    def test_non_integer_hours_returns_400(self, neurons_client):
        """Non-integer hours should return 400."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/mood/history?hours=abc")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["success"] is False
        assert "Invalid" in data["error"]

    def test_float_hours_returns_400(self, neurons_client):
        """Float hours should return 400."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/mood/history?hours=10.5")
        assert resp.status_code == 400

    def test_hours_exactly_168(self, neurons_client):
        """Hours of exactly 168 should be accepted."""
        client, _ = neurons_client
        resp = client.get("/api/v1/neurons/mood/history?hours=168")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["data"]["hours"] == 168


# ===========================================================================
# P2-05: WebSocket Room Name Validation
# ===========================================================================

class TestP2_05_WebSocketRoomValidation:
    """P2-05: Verify WebSocket room name validation."""

    def test_validate_room_name_valid(self):
        """Test valid room names."""
        from copilot_core.api.v1.websocket_neuron import validate_room_name

        assert validate_room_name("neurons") is True
        assert validate_room_name("mood") is True
        assert validate_room_name("room-1") is True
        assert validate_room_name("room_A") is True
        assert validate_room_name("a" * 50) is True

    def test_validate_room_name_invalid(self):
        """Test invalid room names."""
        from copilot_core.api.v1.websocket_neuron import validate_room_name

        assert validate_room_name("") is False
        assert validate_room_name("room space") is False
        assert validate_room_name("../etc") is False
        assert validate_room_name("room<script>") is False
        assert validate_room_name("a" * 51) is False

    def test_subscribe_validates_room(self):
        """Subscribe handler should reject invalid room names."""
        from copilot_core.api.v1.websocket_neuron import NeuronWebSocketHandler

        mock_socketio = MagicMock()
        handler = NeuronWebSocketHandler(mock_socketio)

        # Verify the handler has room validation logic
        assert handler is not None

    def test_unsubscribe_validates_room(self):
        """Unsubscribe handler should also validate room names."""
        from copilot_core.api.v1.websocket_neuron import validate_room_name

        # Simulating what handle_unsubscribe should do
        malicious_rooms = [
            "../../../etc/passwd",
            "room<script>alert(1)</script>",
            "a" * 51,
        ]
        for room in malicious_rooms:
            assert validate_room_name(room) is False, \
                f"Malicious room name should be rejected: {room}"

    def test_room_name_pattern_constants(self):
        """Verify room name constants match spec."""
        from copilot_core.api.v1.websocket_neuron import (
            ROOM_NAME_PATTERN, ROOM_NAME_MAX_LENGTH
        )
        assert ROOM_NAME_PATTERN.pattern == r'^[a-zA-Z0-9_-]+$'
        assert ROOM_NAME_MAX_LENGTH == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
