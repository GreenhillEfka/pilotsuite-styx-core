"""Tests for PilotSuite Hub (v6.0.0)."""

import pytest
from copilot_core.hub.dashboard import (
    DashboardHub,
    DashboardOverview,
    Widget,
    WIDGET_TYPES,
)
from copilot_core.hub.plugin_manager import (
    PluginManager,
    PluginManifest,
    PluginRegistrySummary,
)
from copilot_core.hub.multi_home import (
    MultiHomeManager,
    HomeInstance,
    MultiHomeSummary,
)


# ── Dashboard tests ───────────────────────────────────────────────────────


class TestDashboard:
    """Tests for DashboardHub."""

    def test_default_init(self):
        hub = DashboardHub()
        overview = hub.get_overview()
        assert overview.ok is True
        assert len(overview.widgets) > 0

    def test_default_widgets(self):
        hub = DashboardHub()
        types = hub.get_widget_types()
        assert "energy_overview" in types
        assert "battery_status" in types
        assert "ev_charging" in types

    def test_set_layout(self):
        hub = DashboardHub()
        hub.set_layout("custom", 2, "dark", "en")
        overview = hub.get_overview()
        assert overview.layout["name"] == "custom"
        assert overview.layout["columns"] == 2
        assert overview.layout["theme"] == "dark"

    def test_add_widget(self):
        hub = DashboardHub()
        initial = len(hub.get_widget_types())
        result = hub.add_widget("automation_insights", "Automations", "mdi:robot")
        assert result is True
        assert len(hub.get_widget_types()) == initial + 1

    def test_add_invalid_widget(self):
        hub = DashboardHub()
        result = hub.add_widget("nonexistent_type", "Bad", "mdi:alert")
        assert result is False

    def test_remove_widget(self):
        hub = DashboardHub()
        result = hub.remove_widget("mood_indicator")
        assert result is True
        assert "mood_indicator" not in hub.get_widget_types()

    def test_get_widget(self):
        hub = DashboardHub()
        widget = hub.get_widget("energy_overview")
        assert widget is not None
        assert widget["title"] == "Energie"

    def test_get_nonexistent_widget(self):
        hub = DashboardHub()
        assert hub.get_widget("nonexistent") is None

    def test_update_widget_data(self):
        hub = DashboardHub()
        hub.update_widget_data("energy_overview", {"total_kwh": 42.0})
        widget = hub.get_widget("energy_overview")
        assert widget["data"]["total_kwh"] == 42.0
        assert widget["last_updated"]

    def test_reorder_widgets(self):
        hub = DashboardHub()
        hub.reorder_widgets(["ev_charging", "battery_status", "energy_overview"])
        types = hub.get_widget_types()
        assert types[0] == "ev_charging"
        assert types[1] == "battery_status"
        assert types[2] == "energy_overview"

    def test_register_data_source(self):
        hub = DashboardHub()
        hub.register_data_source("battery", {"status": "charging"})
        overview = hub.get_overview()
        assert "battery" in overview.summary["data_sources"]

    def test_savings_and_alerts(self):
        hub = DashboardHub()
        hub.set_savings(3.45)
        hub.set_alerts_count(2)
        overview = hub.get_overview()
        assert overview.savings_today_eur == 3.45
        assert overview.alerts_count == 2

    def test_overview_generated_at(self):
        hub = DashboardHub()
        overview = hub.get_overview()
        assert overview.generated_at
        assert "T" in overview.generated_at


# ── Plugin Manager tests ─────────────────────────────────────────────────


class TestPluginManager:
    """Tests for PluginManager."""

    def test_default_init(self):
        pm = PluginManager()
        summary = pm.get_summary()
        assert summary.ok is True
        assert summary.total == 6  # 6 built-in plugins

    def test_builtin_plugins_active(self):
        pm = PluginManager()
        summary = pm.get_summary()
        assert summary.active == 6

    def test_get_plugin(self):
        pm = PluginManager()
        info = pm.get_plugin("energy_management")
        assert info is not None
        assert info["name"] == "Energy Management"
        assert info["status"] == "active"

    def test_get_nonexistent_plugin(self):
        pm = PluginManager()
        assert pm.get_plugin("nonexistent") is None

    def test_register_plugin(self):
        pm = PluginManager()
        manifest = PluginManifest(
            "custom_widget", "Custom Widget", "1.0.0",
            author="Test", description="Test plugin",
        )
        result = pm.register_plugin(manifest)
        assert result is True
        assert pm.get_plugin("custom_widget") is not None

    def test_register_duplicate_fails(self):
        pm = PluginManager()
        manifest = PluginManifest("energy_management", "Dup", "1.0.0")
        assert pm.register_plugin(manifest) is False

    def test_register_missing_dependency(self):
        pm = PluginManager()
        manifest = PluginManifest(
            "needs_missing", "Needs Missing", "1.0.0",
            requires=["missing_plugin"],
        )
        assert pm.register_plugin(manifest) is False

    def test_activate_plugin(self):
        pm = PluginManager()
        manifest = PluginManifest("new_plugin", "New", "1.0.0")
        pm.register_plugin(manifest)
        result = pm.activate_plugin("new_plugin")
        assert result is True
        assert pm.get_plugin("new_plugin")["status"] == "active"

    def test_disable_plugin(self):
        pm = PluginManager()
        # mood_engine has no dependents
        result = pm.disable_plugin("mood_engine")
        assert result is True
        assert pm.get_plugin("mood_engine")["status"] == "disabled"

    def test_disable_dependency_blocked(self):
        pm = PluginManager()
        # energy_management is required by heat_pump and ev_charging
        result = pm.disable_plugin("energy_management")
        assert result is False

    def test_configure_plugin(self):
        pm = PluginManager()
        result = pm.configure_plugin("energy_management", {"api_key": "test"})
        assert result is True
        assert pm.get_plugin("energy_management")["config"]["api_key"] == "test"

    def test_categories(self):
        pm = PluginManager()
        summary = pm.get_summary()
        assert "energy" in summary.categories
        assert summary.categories["energy"] == 3

    def test_active_provides(self):
        pm = PluginManager()
        provides = pm.get_active_provides()
        assert "battery_optimizer" in provides
        assert "conversation_agent" in provides


# ── Multi-Home tests ─────────────────────────────────────────────────────


class TestMultiHome:
    """Tests for MultiHomeManager."""

    def test_default_init(self):
        mh = MultiHomeManager()
        assert mh.home_count == 0

    def test_add_home(self):
        mh = MultiHomeManager()
        result = mh.add_home("home1", "Main Home", "Berlin")
        assert result is True
        assert mh.home_count == 1

    def test_add_duplicate_fails(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        assert mh.add_home("home1", "Duplicate") is False

    def test_first_home_is_active(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        assert mh.get_active_home().home_id == "home1"

    def test_switch_active_home(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        mh.add_home("home2", "Holiday Home")
        result = mh.set_active_home("home2")
        assert result is True
        assert mh.get_active_home().home_id == "home2"

    def test_switch_nonexistent_fails(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        assert mh.set_active_home("nonexistent") is False

    def test_remove_home(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        result = mh.remove_home("home1")
        assert result is True
        assert mh.home_count == 0

    def test_remove_active_switches(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        mh.add_home("home2", "Holiday Home")
        mh.remove_home("home1")
        assert mh.get_active_home().home_id == "home2"

    def test_get_home(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home", "Berlin", 52.52, 13.405)
        info = mh.get_home("home1")
        assert info["name"] == "Main Home"
        assert info["latitude"] == 52.52
        assert info["is_active"] is True

    def test_update_status(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main Home")
        mh.update_home_status("home1", device_count=42, energy_kwh=15.3, cost_eur=4.59)
        info = mh.get_home("home1")
        assert info["device_count"] == 42
        assert info["energy_today_kwh"] == 15.3
        assert info["cost_today_eur"] == 4.59

    def test_summary(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main")
        mh.add_home("home2", "Holiday")
        mh.update_home_status("home1", device_count=30, energy_kwh=10.0, cost_eur=3.0)
        mh.update_home_status("home2", device_count=12, energy_kwh=5.0, cost_eur=1.5)
        summary = mh.get_summary()
        assert summary.total_homes == 2
        assert summary.online_homes == 2
        assert summary.total_devices == 42
        assert summary.total_energy_kwh == 15.0
        assert summary.total_cost_eur == 4.5

    def test_home_ids(self):
        mh = MultiHomeManager()
        mh.add_home("a", "Alpha")
        mh.add_home("b", "Beta")
        assert "a" in mh.home_ids
        assert "b" in mh.home_ids

    def test_offline_home(self):
        mh = MultiHomeManager()
        mh.add_home("home1", "Main")
        mh.update_home_status("home1", status="offline")
        summary = mh.get_summary()
        assert summary.online_homes == 0
