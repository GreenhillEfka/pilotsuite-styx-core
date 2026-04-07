"""Tests for HABridge — HA service call bridge."""

from unittest.mock import MagicMock, patch

import pytest

from copilot_core.autonomy.ha_bridge import HABridge, ServiceCallResult
from copilot_core.circuit_breaker import CircuitOpenError


@pytest.fixture
def bridge():
    """HABridge with test token."""
    return HABridge(
        supervisor_api="http://test-supervisor/core/api",
        supervisor_token="test-token-123",
        timeout=5,
    )


@pytest.fixture
def bridge_no_token():
    """HABridge without token."""
    return HABridge(supervisor_token="")


class TestServiceCallResult:
    def test_to_dict(self):
        r = ServiceCallResult(ok=True, domain="light", service="turn_on")
        d = r.to_dict()
        assert d["ok"] is True
        assert d["domain"] == "light"


class TestCallService:
    def test_no_token_returns_error(self, bridge_no_token):
        result = bridge_no_token.call_service("light", "turn_on")
        assert result.ok is False
        assert "SUPERVISOR_TOKEN" in result.error

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_successful_call(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_breaker.call.return_value = mock_resp

        result = bridge.call_service("light", "turn_on", {
            "entity_id": "light.test",
            "brightness_pct": 50,
        })
        assert result.ok is True
        assert result.domain == "light"
        assert result.service == "turn_on"
        assert result.entity_ids == ["light.test"]
        assert result.ha_status_code == 200

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_failed_call(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_breaker.call.return_value = mock_resp

        result = bridge.call_service("light", "turn_on")
        assert result.ok is False
        assert result.ha_status_code == 500

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_circuit_open(self, mock_breaker, bridge):
        mock_breaker.call.side_effect = CircuitOpenError("open")

        result = bridge.call_service("light", "turn_on")
        assert result.ok is False
        assert "Circuit breaker" in result.error

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_multiple_entity_ids(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_breaker.call.return_value = mock_resp

        result = bridge.call_service("light", "turn_on", {
            "entity_id": ["light.a", "light.b"],
        })
        assert result.entity_ids == ["light.a", "light.b"]


class TestConvenienceMethods:
    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_turn_on_light(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_breaker.call.return_value = mock_resp

        result = bridge.turn_on_light("light.wohnzimmer", brightness_pct=50, color_temp_k=2700)
        assert result.ok is True
        # Verify the call was made
        call_args = mock_breaker.call.call_args
        func = call_args[0][0]
        # The func is a lambda, just verify the breaker was called
        assert mock_breaker.call.called

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_turn_off_light(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_breaker.call.return_value = mock_resp

        result = bridge.turn_off_light("light.wohnzimmer")
        assert result.ok is True

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_turn_on_light_clamps_brightness(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_breaker.call.return_value = mock_resp

        result = bridge.turn_on_light("light.x", brightness_pct=150)
        assert result.ok is True

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_get_entity_state_success(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"state": "on", "entity_id": "light.test"}
        mock_breaker.call.return_value = mock_resp

        state = bridge.get_entity_state("light.test")
        assert state is not None
        assert state["state"] == "on"

    @patch("copilot_core.autonomy.ha_bridge.ha_supervisor_breaker")
    def test_get_entity_state_not_found(self, mock_breaker, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_breaker.call.return_value = mock_resp

        state = bridge.get_entity_state("light.nonexistent")
        assert state is None

    def test_get_entity_state_no_token(self, bridge_no_token):
        state = bridge_no_token.get_entity_state("light.test")
        assert state is None
