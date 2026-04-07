"""HomeAssistant Integration Package.

Provides async client, auto-discovery, entity mapping, and WebSocket event
handling.

The package import itself must stay lightweight so focused imports such as
``copilot_core.homeassistant.zone_matcher`` do not fail just because optional
runtime clients (for example aiohttp-backed HA clients) are unavailable.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from pkgutil import extend_path
from typing import Any, Dict, Tuple


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_runtime_pkg_dir = (
    _pkg_dir.parent / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "homeassistant"
)
_runtime_pkg_path = str(_runtime_pkg_dir)

if _runtime_pkg_dir.is_dir() and _runtime_pkg_path not in __path__:
    __path__.append(_runtime_pkg_path)


_LAZY_EXPORTS: Dict[str, Tuple[str, str]] = {
    # Client
    "HomeAssistantClient": (".client", "HomeAssistantClient"),
    "HAConnectionConfig": (".client", "HAConnectionConfig"),
    "HAConnectionStatus": (".client", "HAConnectionStatus"),
    # Auto-discovery
    "AutoDiscovery": (".auto_discovery", "AutoDiscovery"),
    "DiscoveredInstance": (".auto_discovery", "DiscoveredInstance"),
    # Entity mapping
    "EntityMapper": (".entity_mapper", "EntityMapper"),
    "EntityMapping": (".entity_mapper", "EntityMapping"),
    "WidgetType": (".entity_mapper", "WidgetType"),
    "SensorDeviceClass": (".entity_mapper", "SensorDeviceClass"),
    # WebSocket client
    "HomeAssistantWebSocketClient": (".websocket_client", "HomeAssistantWebSocketClient"),
    "WebSocketConfig": (".websocket_client", "WebSocketConfig"),
    "WebSocketStatus": (".websocket_client", "WebSocketStatus"),
    "ConnectionState": (".websocket_client", "ConnectionState"),
    # Event handling
    "EventHandler": (".event_handler", "EventHandler"),
    "HAEvent": (".event_handler", "HAEvent"),
    "EventQueue": (".event_handler", "EventQueue"),
    "EventHistory": (".event_handler", "EventHistory"),
    "EventType": (".event_handler", "EventType"),
    "create_standard_subscriptions": (".event_handler", "create_standard_subscriptions"),
    # API blueprints
    "ha_discovery_bp": (".api", "ha_discovery_bp"),
    "init_ha_discovery_api": (".api", "init_ha_discovery_api"),
    "ha_events_bp": ("..api.v1.ha_events", "ha_events_bp"),
    "init_ha_events_api": ("..api.v1.ha_events", "init_ha_events_api"),
    "register_socketio_handlers": ("..api.v1.ha_events", "register_socketio_handlers"),
}


__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
