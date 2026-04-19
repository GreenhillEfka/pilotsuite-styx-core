"""MQTT Client Integration for PilotSuite (F8.5).

Minimal MQTT client wrapper that connects to the Home Assistant MQTT broker.
Falls back gracefully when broker is unavailable.

Supports:
- Connection to HA-managed MQTT broker (supervisor)
- Publishing messages to topics
- Subscription callbacks
- Connection status reporting

Requires: `paho-mqtt` package. Without it, returns stubbed unavailable state.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

# Try to import paho-mqtt; stub if not available
try:
    import paho.mqtt.client as mqtt
    _MQTT_AVAILABLE = True
except Exception:  # noqa: BLE001
    mqtt = None
    _MQTT_AVAILABLE = False


class MQTTClient:
    """Minimal MQTT client with HA-broker defaults.

    Args:
        broker_host: MQTT broker host. Defaults to Home Assistant Supervisor broker.
        broker_port: MQTT broker port. Defaults to 1883.
        topic_prefix: Prefix prepended to all topics (e.g. "pilotsuite/").
        username: Optional MQTT username.
        password: Optional MQTT password.
    """

    def __init__(
        self,
        broker_host: str = "172.30.33.1",  # HA Supervisor default
        broker_port: int = 1883,
        topic_prefix: str = "pilotsuite/",
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._topic_prefix = topic_prefix
        self._username = username
        self._password = password
        self._client: Any = None
        self._connected = False
        self._subscriptions: dict[str, Callable] = {}

        if not _MQTT_AVAILABLE:
            _LOGGER.warning("paho-mqtt not installed — MQTT client is stubbed")
            return

        client_id = f"pilotsuite_{id(self)}"
        self._client = mqtt.Client(client_id=client_id)

        if username and password:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            _LOGGER.info("MQTT connected to %s:%s", self._broker_host, self._broker_port)
            # Resubscribe to saved topics
            for topic in self._subscriptions:
                client.subscribe(topic)
        else:
            _LOGGER.warning("MQTT connection failed with code %s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        _LOGGER.warning("MQTT disconnected (rc=%s)", rc)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        if topic in self._subscriptions:
            self._subscriptions[topic](msg.payload.decode("utf-8", errors="replace"))

    def connect(self, timeout_ms: int = 5000) -> bool:
        """Connect to the MQTT broker. Returns True on success."""
        if not _MQTT_AVAILABLE or self._client is None:
            return False
        try:
            self._client.connect(self._broker_host, self._broker_port, keepalive=timeout_ms // 1000)
            self._client.loop_start()
            return True
        except Exception as exc:
            _LOGGER.error("MQTT connect failed: %s", exc)
            return False

    def publish(self, topic: str, payload: str | bytes, qos: int = 0) -> bool:
        """Publish a message to a topic. Returns True on success."""
        if not self._connected:
            return False
        if not _MQTT_AVAILABLE or self._client is None:
            return False
        try:
            full_topic = f"{self._topic_prefix}{topic}"
            self._client.publish(full_topic, payload, qos=qos)
            return True
        except Exception as exc:
            _LOGGER.error("MQTT publish failed: %s", exc)
            return False

    def subscribe(self, topic: str, callback: Callable[[str], None]) -> bool:
        """Subscribe to a topic with a callback. Returns True on success."""
        if not _MQTT_AVAILABLE or self._client is None:
            return False
        try:
            full_topic = f"{self._topic_prefix}{topic}"
            self._client.subscribe(full_topic)
            self._subscriptions[full_topic] = callback
            return True
        except Exception as exc:
            _LOGGER.error("MQTT subscribe failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Disconnect from the broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to the broker."""
        return self._connected

    def status_summary(self) -> dict[str, Any]:
        """Return status dict for the /mqtt/status endpoint."""
        return {
            "mqtt_available": _MQTT_AVAILABLE,
            "connected": self._connected,
            "broker_host": self._broker_host,
            "broker_port": self._broker_port,
            "topic_prefix": self._topic_prefix,
            "active_subscriptions": len(self._subscriptions),
        }


# Module-level singleton (lazy, created on first access)
_mqtt_client: MQTTClient | None = None


def get_mqtt_client() -> MQTTClient:
    """Get or create the module-level MQTTClient singleton."""
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = MQTTClient()
    return _mqtt_client