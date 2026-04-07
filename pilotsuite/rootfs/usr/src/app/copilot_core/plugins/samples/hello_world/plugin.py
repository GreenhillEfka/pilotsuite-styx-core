"""Hello World Sample Plugin for PilotSuite.

This plugin demonstrates the basic plugin lifecycle and hook callbacks.

To test it:
1. Copy this directory to your plugins/ directory
2. Restart PilotSuite Core
3. The plugin will be auto-discovered and loaded

Or programmatically::

    from copilot_core.plugins.engine import create_plugin_engine

    engine = create_plugin_engine(plugin_dirs=["copilot_core/plugins/samples"])
    engine.discover_plugins()
    engine.enable_plugin("hello_world", config={"message": "Custom hello!"})
"""

import logging

logger = logging.getLogger(__name__)

# Module-level config (set by on_enable)
_config: dict = {}


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------

def on_enable(config: dict) -> None:
    """Called when the plugin is enabled.

    Args:
        config: Runtime configuration dict (from store + API call).
    """
    global _config
    _config = dict(config)

    message = _config.get("message", "Hello from Hello World plugin!")
    count = _config.get("greeting_count", 3)

    for i in range(count):
        logger.info("[hello_world] %s  (%d/%d)", message, i + 1, count)


def on_disable() -> None:
    """Called when the plugin is disabled."""
    logger.info("[hello_world] Plugin disabled. Goodbye!")


def on_unload() -> None:
    """Called when the plugin module is unloaded from memory."""
    logger.debug("[hello_world] Module unloaded.")


def on_startup() -> None:
    """Called once when the PilotSuite core starts."""
    logger.info("[hello_world] Core startup complete.")


def on_shutdown() -> None:
    """Called once when the PilotSuite core shuts down."""
    logger.info("[hello_world] Core shutdown — plugin signing off.")


# ---------------------------------------------------------------------------
# Event hook
# ---------------------------------------------------------------------------

def on_event(event: dict) -> dict | None:
    """Handle Home Assistant events.

    This plugin logs every event it sees and returns a enriched version
    with a ``hello_world`` key stamped.

    Args:
        event: The raw event dict from Home Assistant.

    Returns:
        A modified event dict, or None to indicate the event was consumed
        without producing a response.
    """
    event_type = event.get("event_type", "<unknown>")
    logger.debug("[hello_world] Received event type=%s", event_type)

    # Attach plugin metadata to prove we processed it
    enriched = dict(event)
    enriched["_hello_world_processed"] = True
    enriched["_hello_world_plugin_version"] = "1.0.0"
    return enriched


# ---------------------------------------------------------------------------
# Optional: named hook implementations (alternative to function-name convention)
# ---------------------------------------------------------------------------

# The PluginEngine uses function-name matching by default.
# You can also expose hooks as named attributes if your framework requires it:
#
# HOOKS = {
#     "on_event": on_event,
#     "on_startup": on_startup,
#     "on_shutdown": on_shutdown,
# }
