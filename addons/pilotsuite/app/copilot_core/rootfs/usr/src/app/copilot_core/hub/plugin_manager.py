"""Plugin Manager for PilotSuite Hub (v6.0.0).

Manages installable plugins that extend PilotSuite functionality.
Plugins can add widgets, API endpoints, sensors, and automations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    """Plugin descriptor."""

    plugin_id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    category: str = "general"  # energy, comfort, security, automation, general
    icon: str = "mdi:puzzle"
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginState:
    """Runtime state of a plugin."""

    plugin_id: str
    status: str = "installed"  # installed, active, disabled, error
    installed_at: str = ""
    last_active: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class PluginRegistrySummary:
    """Summary of all plugins."""

    total: int = 0
    active: int = 0
    disabled: int = 0
    error: int = 0
    plugins: list[dict[str, Any]] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    ok: bool = True


# ── Built-in plugin manifests ─────────────────────────────────────────────

_BUILTIN_PLUGINS = [
    PluginManifest(
        "energy_management", "Energy Management", "1.0.0",
        author="PilotSuite", description="Battery, solar, tariff optimization",
        category="energy", icon="mdi:flash",
        provides=["battery_optimizer", "tariff_engine", "energy_forecast"],
    ),
    PluginManifest(
        "heat_pump", "Heat Pump Controller", "1.0.0",
        author="PilotSuite", description="COP-optimized heat pump scheduling",
        category="energy", icon="mdi:heat-pump",
        requires=["energy_management"],
        provides=["heat_pump_controller"],
    ),
    PluginManifest(
        "ev_charging", "EV Charging Planner", "1.0.0",
        author="PilotSuite", description="Smart EV charging from tariff+solar",
        category="energy", icon="mdi:ev-station",
        requires=["energy_management"],
        provides=["ev_charging_planner"],
    ),
    PluginManifest(
        "weather_integration", "Weather & Warnings", "1.0.0",
        author="PilotSuite", description="DWD weather warnings and forecasts",
        category="general", icon="mdi:weather-cloudy-alert",
        provides=["weather_warnings", "proactive_alerts"],
    ),
    PluginManifest(
        "mood_engine", "Mood & Comfort Engine", "1.0.0",
        author="PilotSuite", description="Neural mood system and comfort tracking",
        category="comfort", icon="mdi:emoticon",
        provides=["mood_sensor", "comfort_index"],
    ),
    PluginManifest(
        "styx_agent", "Styx Conversation Agent", "1.0.0",
        author="PilotSuite", description="AI conversation agent with LLM backend",
        category="automation", icon="mdi:robot",
        provides=["conversation_agent", "onboarding"],
    ),
]


class PluginManager:
    """Manages PilotSuite plugins.

    Handles plugin lifecycle: install, activate, disable, configure.
    Validates dependencies and provides plugin discovery.
    """

    CATEGORIES = ("energy", "comfort", "security", "automation", "general")

    def __init__(self) -> None:
        self._manifests: dict[str, PluginManifest] = {}
        self._states: dict[str, PluginState] = {}
        self._hooks: dict[str, list[Callable]] = {}

        # Register built-in plugins
        for manifest in _BUILTIN_PLUGINS:
            self._manifests[manifest.plugin_id] = manifest
            self._states[manifest.plugin_id] = PluginState(
                plugin_id=manifest.plugin_id,
                status="active",
                installed_at=datetime.now(timezone.utc).isoformat(),
                last_active=datetime.now(timezone.utc).isoformat(),
            )

    def register_plugin(self, manifest: PluginManifest) -> bool:
        """Register a new plugin."""
        if manifest.plugin_id in self._manifests:
            return False

        # Validate dependencies
        for req in manifest.requires:
            if req not in self._manifests:
                logger.warning(
                    "Plugin %s requires %s which is not installed",
                    manifest.plugin_id, req,
                )
                return False

        self._manifests[manifest.plugin_id] = manifest
        self._states[manifest.plugin_id] = PluginState(
            plugin_id=manifest.plugin_id,
            status="installed",
            installed_at=datetime.now(timezone.utc).isoformat(),
        )
        return True

    def activate_plugin(self, plugin_id: str) -> bool:
        """Activate a plugin."""
        if plugin_id not in self._states:
            return False
        state = self._states[plugin_id]

        # Check dependencies are active
        manifest = self._manifests.get(plugin_id)
        if manifest:
            for req in manifest.requires:
                req_state = self._states.get(req)
                if not req_state or req_state.status != "active":
                    state.error = f"Dependency {req} not active"
                    return False

        state.status = "active"
        state.last_active = datetime.now(timezone.utc).isoformat()
        state.error = ""
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        if plugin_id not in self._states:
            return False

        # Check no active plugin depends on this one
        provides = set()
        manifest = self._manifests.get(plugin_id)
        if manifest:
            provides = set(manifest.provides)

        for pid, m in self._manifests.items():
            if pid != plugin_id and self._states.get(pid, PluginState(pid)).status == "active":
                for req in m.requires:
                    if req == plugin_id:
                        return False  # Cannot disable: dependency

        self._states[plugin_id].status = "disabled"
        return True

    def configure_plugin(self, plugin_id: str, config: dict[str, Any]) -> bool:
        """Update plugin configuration."""
        if plugin_id not in self._states:
            return False
        self._states[plugin_id].config = config
        return True

    def get_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        """Get plugin info."""
        manifest = self._manifests.get(plugin_id)
        state = self._states.get(plugin_id)
        if not manifest or not state:
            return None
        return {
            "plugin_id": manifest.plugin_id,
            "name": manifest.name,
            "version": manifest.version,
            "author": manifest.author,
            "description": manifest.description,
            "category": manifest.category,
            "icon": manifest.icon,
            "requires": manifest.requires,
            "provides": manifest.provides,
            "status": state.status,
            "installed_at": state.installed_at,
            "last_active": state.last_active,
            "config": state.config,
            "error": state.error,
        }

    def get_summary(self) -> PluginRegistrySummary:
        """Get plugin registry summary."""
        plugins = []
        categories: dict[str, int] = {}

        for pid in self._manifests:
            info = self.get_plugin(pid)
            if info:
                plugins.append(info)
                cat = info.get("category", "general")
                categories[cat] = categories.get(cat, 0) + 1

        active = sum(1 for s in self._states.values() if s.status == "active")
        disabled = sum(1 for s in self._states.values() if s.status == "disabled")
        error = sum(1 for s in self._states.values() if s.status == "error")

        return PluginRegistrySummary(
            total=len(plugins),
            active=active,
            disabled=disabled,
            error=error,
            plugins=plugins,
            categories=categories,
        )

    def get_active_provides(self) -> list[str]:
        """Get all capabilities provided by active plugins."""
        provides = []
        for pid, state in self._states.items():
            if state.status == "active":
                manifest = self._manifests.get(pid)
                if manifest:
                    provides.extend(manifest.provides)
        return provides
