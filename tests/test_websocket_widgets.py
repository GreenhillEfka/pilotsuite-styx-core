"""Contract tests for WebSocket Widgets — Slice 176."""
import unittest

try:
    from copilot_core.websocket.widgets import (
        WidgetWebSocketManager,
        get_widget_ws_manager,
        handle_entity_change
    )
except ModuleNotFoundError:
    WidgetWebSocketManager = None
    get_widget_ws_manager = None
    handle_entity_change = None


class TestWidgetWebSocketManager(unittest.TestCase):
    """Test WebSocket widget manager."""

    def test_manager_creation(self):
        """WidgetWebSocketManager can be created."""
        if not WidgetWebSocketManager:
            self.skipTest("websocket.widgets not available")
        manager = WidgetWebSocketManager()
        self.assertIsNotNone(manager)

    def test_subscribe_adds_connection(self):
        """Subscribe adds client to connection set."""
        if not WidgetWebSocketManager:
            self.skipTest("websocket.widgets not available")
        manager = WidgetWebSocketManager()
        mock_client = object()
        manager.subscribe(mock_client, "floorplan", "fp1")
        channel = "widget:floorplan:fp1"
        self.assertIn(channel, manager._connections)
        self.assertIn(mock_client, manager._connections[channel])

    def test_unsubscribe_removes_connection(self):
        """Unsubscribe removes client from connection set."""
        if not WidgetWebSocketManager:
            self.skipTest("websocket.widgets not available")
        manager = WidgetWebSocketManager()
        mock_client = object()
        manager.subscribe(mock_client, "floorplan", "fp1")
        manager.unsubscribe(mock_client, "floorplan", "fp1")
        channel = "widget:floorplan:fp1"
        self.assertNotIn(mock_client, manager._connections[channel])

    def test_get_global_manager(self):
        """get_widget_ws_manager returns singleton."""
        if not get_widget_ws_manager:
            self.skipTest("websocket.widgets not available")
        manager1 = get_widget_ws_manager()
        manager2 = get_widget_ws_manager()
        self.assertIs(manager1, manager2)


class TestEntityChangeHandler(unittest.TestCase):
    """Test entity change broadcast handler."""

    def test_handler_exists(self):
        """handle_entity_change function exists."""
        if not handle_entity_change:
            self.skipTest("websocket.widgets not available")
        self.assertTrue(callable(handle_entity_change))


if __name__ == "__main__":
    unittest.main()
