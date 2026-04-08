"""Tests for Neuron WebSocket Handler."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Mock flask_socketio before importing websocket_neuron module,
# then restore original modules to avoid polluting other tests.
import sys

_original_flask = sys.modules.get('flask')
_original_flask_socketio = sys.modules.get('flask_socketio')

mock_socketio_module = MagicMock()
mock_socketio_module.SocketIO = MagicMock()
mock_socketio_module.emit = MagicMock()
mock_socketio_module.join_room = MagicMock()
mock_socketio_module.leave_room = MagicMock()
sys.modules['flask_socketio'] = mock_socketio_module

mock_flask = MagicMock()
mock_flask.request = MagicMock()
sys.modules['flask'] = mock_flask

from copilot_core.api.v1.websocket_neuron import (
    NeuronWebSocketHandler,
    get_neuron_ws_handler,
    init_neuron_websocket,
    EVENT_NEURON_UPDATE,
    EVENT_NEURON_FIRE,
    EVENT_GRAPH_UPDATE,
    EVENT_MOOD_CHANGE,
    EVENT_SUGGESTION
)

# Restore original modules so other test files are not affected
if _original_flask is not None:
    sys.modules['flask'] = _original_flask
else:
    del sys.modules['flask']

if _original_flask_socketio is not None:
    sys.modules['flask_socketio'] = _original_flask_socketio
else:
    del sys.modules['flask_socketio']


class TestNeuronWebSocketHandler:
    """Tests for NeuronWebSocketHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.handler = NeuronWebSocketHandler()
    
    def test_init_without_socketio(self):
        """Test initialization without SocketIO."""
        handler = NeuronWebSocketHandler()
        assert handler.socketio is None
        assert len(handler.connected_clients) == 0
    
    def test_init_with_socketio(self):
        """Test initialization with SocketIO."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler(mock_socketio)
        assert handler.socketio is mock_socketio
    
    def test_init_app(self):
        """Test init_app method."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler()
        handler.init_app(mock_socketio)
        
        assert handler.socketio is mock_socketio
    
    def test_broadcast_neuron_update_no_socketio(self):
        """Test broadcast with no SocketIO (should not crash)."""
        handler = NeuronWebSocketHandler()
        
        # Should not raise
        handler.broadcast_neuron_update("context.presence", {"value": 0.8})
    
    @patch('copilot_core.api.v1.websocket_neuron.datetime')
    def test_broadcast_neuron_update(self, mock_datetime):
        """Test broadcasting neuron update."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler(mock_socketio)
        
        mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        
        handler.broadcast_neuron_update("context.presence", {
            "value": 0.8,
            "confidence": 0.9
        })
        
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == EVENT_NEURON_UPDATE
        assert call_args[0][1]["neuron_id"] == "context.presence"
        assert call_args[0][1]["data"]["value"] == 0.8
    
    def test_broadcast_neuron_fire(self):
        """Test broadcasting neuron fire event."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler(mock_socketio)
        
        handler.broadcast_neuron_fire("mood.focus", 0.95, 0.98)
        
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == EVENT_NEURON_FIRE
        assert call_args[0][1]["neuron_id"] == "mood.focus"
        assert call_args[0][1]["data"]["value"] == 0.95
    
    def test_broadcast_graph_update(self):
        """Test broadcasting graph update."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler(mock_socketio)
        
        graph_data = {
            "nodes": [{"id": "context.presence"}],
            "edges": [{"source": "context.presence", "target": "state.energy"}]
        }
        
        handler.broadcast_graph_update(graph_data)
        
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == EVENT_GRAPH_UPDATE
        assert "nodes" in call_args[0][1]["data"]
    
    def test_broadcast_mood_change(self):
        """Test broadcasting mood change."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler(mock_socketio)
        
        handler.broadcast_mood_change(
            mood="focus",
            confidence=0.87,
            mood_values={"focus": 0.87, "relax": 0.45}
        )
        
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == EVENT_MOOD_CHANGE
        assert call_args[0][1]["data"]["mood"] == "focus"
        assert call_args[0][1]["data"]["confidence"] == 0.87
    
    def test_broadcast_suggestion(self):
        """Test broadcasting suggestion."""
        mock_socketio = Mock()
        handler = NeuronWebSocketHandler(mock_socketio)
        
        suggestion = {
            "action": "turn_on_lights",
            "reason": "Dark room detected",
            "priority": "medium"
        }
        
        handler.broadcast_suggestion(suggestion)
        
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == EVENT_SUGGESTION
        assert call_args[0][1]["data"]["action"] == "turn_on_lights"
    
    def test_get_connected_count(self):
        """Test getting connected client count."""
        handler = NeuronWebSocketHandler()
        handler.connected_clients = {"client1", "client2", "client3"}
        
        count = handler.get_connected_count()
        assert count == 3
    
    def test_get_client_info(self):
        """Test getting client info."""
        handler = NeuronWebSocketHandler()
        handler.connected_clients = {"client1"}
        handler.client_rooms = {"client1": "neurons"}
        
        info = handler.get_client_info("client1")
        
        assert info is not None
        assert info["client_id"] == "client1"
        assert info["room"] == "neurons"
        assert info["connected"] is True
    
    def test_get_client_info_not_connected(self):
        """Test getting info for non-connected client."""
        handler = NeuronWebSocketHandler()
        
        info = handler.get_client_info("unknown_client")
        
        assert info is None


class TestWebSocketEventTypes:
    """Tests for WebSocket event type constants."""
    
    def test_event_types_are_strings(self):
        """Test event types are defined as strings."""
        assert isinstance(EVENT_NEURON_UPDATE, str)
        assert isinstance(EVENT_NEURON_FIRE, str)
        assert isinstance(EVENT_GRAPH_UPDATE, str)
        assert isinstance(EVENT_MOOD_CHANGE, str)
        assert isinstance(EVENT_SUGGESTION, str)
    
    def test_event_types_are_unique(self):
        """Test event types are unique."""
        events = [
            EVENT_NEURON_UPDATE,
            EVENT_NEURON_FIRE,
            EVENT_GRAPH_UPDATE,
            EVENT_MOOD_CHANGE,
            EVENT_SUGGESTION
        ]
        
        assert len(events) == len(set(events))


class TestWebSocketSingleton:
    """Tests for WebSocket handler singleton."""
    
    def teardown_method(self):
        """Reset singleton after each test."""
        import copilot_core.api.v1.websocket_neuron as ws_module
        ws_module._ws_handler = None
    
    def test_get_neuron_ws_handler_returns_singleton(self):
        """Test get_neuron_ws_handler returns same instance."""
        handler1 = get_neuron_ws_handler()
        handler2 = get_neuron_ws_handler()
        
        assert handler1 is handler2
    
    def test_init_neuron_websocket(self):
        """Test init_neuron_websocket function."""
        mock_socketio = Mock()
        
        # Should not raise
        init_neuron_websocket(mock_socketio)


class TestWebSocketIntegration:
    """Integration tests for WebSocket handler."""
    
    def test_handler_lifecycle(self):
        """Test complete handler lifecycle."""
        # Create handler
        handler = NeuronWebSocketHandler()
        
        # Mock socketio
        mock_socketio = Mock()
        handler.init_app(mock_socketio)
        
        # Broadcast various events
        handler.broadcast_neuron_update("context.presence", {"value": 0.8})
        handler.broadcast_neuron_fire("mood.focus", 0.9, 0.95)
        handler.broadcast_graph_update({"nodes": [], "edges": []})
        handler.broadcast_mood_change("focus", 0.8, {"focus": 0.8})
        handler.broadcast_suggestion({"action": "test"})
        
        # Verify emits were called
        assert mock_socketio.emit.call_count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
