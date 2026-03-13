"""
Performance API — WebSocket and dashboard performance metrics.

Blueprint prefix: /api/v1/performance
"""
from __future__ import annotations

import time
import threading
from typing import Any, Dict

from flask import Blueprint, jsonify

performance_bp = Blueprint(
    "performance", __name__, url_prefix="/api/v1/performance"
)

_metrics_lock = threading.Lock()
_websocket_metrics: Dict[str, Any] = {
    "connections": 0,
    "messages_sent": 0,
    "messages_received": 0,
    "batch_updates": 0,
    "compression_savings_bytes": 0,
    "last_updated": None,
}


def update_websocket_metrics(
    connections: int = 0,
    messages_sent: int = 0,
    messages_received: int = 0,
    batch_updates: int = 0,
    compression_savings: int = 0,
) -> None:
    """Update WebSocket performance metrics (thread-safe)."""
    with _metrics_lock:
        _websocket_metrics["connections"] = connections
        _websocket_metrics["messages_sent"] += messages_sent
        _websocket_metrics["messages_received"] += messages_received
        _websocket_metrics["batch_updates"] += batch_updates
        _websocket_metrics["compression_savings_bytes"] += compression_savings
        _websocket_metrics["last_updated"] = time.time()


def track_performance(func):
    """Decorator to track function execution time."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed_ms = (time.time() - start) * 1000
        with _metrics_lock:
            _websocket_metrics.setdefault("tracked_calls", [])
            _websocket_metrics["tracked_calls"].append({
                "function": func.__name__,
                "elapsed_ms": round(elapsed_ms, 2),
                "timestamp": time.time(),
            })
            # Keep only last 100 tracked calls
            if len(_websocket_metrics["tracked_calls"]) > 100:
                _websocket_metrics["tracked_calls"] = _websocket_metrics["tracked_calls"][-100:]
        return result
    wrapper.__name__ = func.__name__
    return wrapper


@performance_bp.route("", methods=["GET"])
def get_websocket_metrics():
    """Get current WebSocket performance metrics."""
    with _metrics_lock:
        return jsonify({"ok": True, **_websocket_metrics})


@performance_bp.route("/reset", methods=["POST"])
def reset_metrics():
    """Reset performance metrics."""
    with _metrics_lock:
        _websocket_metrics["messages_sent"] = 0
        _websocket_metrics["messages_received"] = 0
        _websocket_metrics["batch_updates"] = 0
        _websocket_metrics["compression_savings_bytes"] = 0
        _websocket_metrics["tracked_calls"] = []
        _websocket_metrics["last_updated"] = time.time()
    return jsonify({"ok": True, "status": "reset"})
