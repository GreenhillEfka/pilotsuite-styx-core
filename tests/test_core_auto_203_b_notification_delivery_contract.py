"""CORE-AUTO-203-B proof ring: proactive notification delivery contract."""

from unittest.mock import Mock, patch

import requests

from copilot_core.proactive_engine import ProactiveContextEngine


class TestCoreAuto203BNotificationDeliveryContract:
    """CORE-AUTO-203-B: delivery stays on the existing notification seam only."""

    def test_notification_delivery_fails_without_supervisor_token(self):
        """No token keeps the seam on the canonical no-token failure path."""
        engine = ProactiveContextEngine()

        with patch.dict("os.environ", {}, clear=True), patch(
            "copilot_core.proactive_engine.requests.post"
        ) as post:
            result = engine.deliver_suggestion(
                {"type": "automation", "message": "Zone alert in wohnzimmer"},
                method="notification",
            )

        assert result == {"ok": False, "error": "No SUPERVISOR_TOKEN"}
        post.assert_not_called()

    def test_notification_delivery_posts_bearer_auth_to_persistent_notification(self):
        """Notification delivery uses the canonical HA persistent-notification service."""
        engine = ProactiveContextEngine()
        response = Mock()
        response.raise_for_status.return_value = None

        with patch.dict(
            "os.environ",
            {
                "SUPERVISOR_TOKEN": "secret-token",
                "SUPERVISOR_API": "http://supervisor",
            },
            clear=True,
        ), patch("copilot_core.proactive_engine.requests.post", return_value=response) as post:
            result = engine.deliver_suggestion(
                {"type": "automation", "message": "Zone alert in wohnzimmer"},
                method="notification",
            )

        assert result == {"ok": True, "method": "notification"}
        post.assert_called_once_with(
            "http://supervisor/services/notify/persistent_notification",
            json={"message": "Zone alert in wohnzimmer", "title": "Styx"},
            headers={
                "Authorization": "Bearer secret-token",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status.assert_called_once_with()

    def test_notification_delivery_returns_request_failure_error(self):
        """Request failures stay file-backed as an explicit delivery error."""
        engine = ProactiveContextEngine()

        with patch.dict(
            "os.environ",
            {
                "SUPERVISOR_TOKEN": "secret-token",
                "SUPERVISOR_API": "http://supervisor",
            },
            clear=True,
        ), patch(
            "copilot_core.proactive_engine.requests.post",
            side_effect=requests.RequestException("supervisor unavailable"),
        ):
            result = engine.deliver_suggestion(
                {"type": "automation", "message": "Zone alert in wohnzimmer"},
                method="notification",
            )

        assert result == {"ok": False, "error": "supervisor unavailable"}

    def test_notification_delivery_returns_http_error_from_failed_response(self):
        """HTTP failures do not report a false-positive notification success."""
        engine = ProactiveContextEngine()
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("503 Server Error")

        with patch.dict(
            "os.environ",
            {
                "SUPERVISOR_TOKEN": "secret-token",
                "SUPERVISOR_API": "http://supervisor",
            },
            clear=True,
        ), patch("copilot_core.proactive_engine.requests.post", return_value=response):
            result = engine.deliver_suggestion(
                {"type": "automation", "message": "Zone alert in wohnzimmer"},
                method="notification",
            )

        assert result == {"ok": False, "error": "503 Server Error"}
