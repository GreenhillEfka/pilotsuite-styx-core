"""Tests fuer ModuleRouter und Netzwerk-Modul Config/Refresh."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from copilot_core.hub.module_router import ModuleRouter
from copilot_core.hub.zwave_module import ZWaveModuleEngine
from copilot_core.hub.zigbee_module import ZigbeeModuleEngine
from copilot_core.hub.thread_module import ThreadModuleEngine
from copilot_core.hub.homeassistant_module import HomeAssistantModuleEngine


# -- Engine Config Tests -------------------------------------------------------


class TestEngineConfig:
    """Testet get_config/update_config der einzelnen Engines."""

    def test_zwave_default_config(self):
        engine = ZWaveModuleEngine()
        cfg = engine.get_config()
        assert cfg["enabled"] is True
        assert cfg["polling_interval_s"] == 120
        assert cfg["alert_dead_devices"] is True

    def test_zwave_update_config(self):
        engine = ZWaveModuleEngine()
        updated = engine.update_config({"polling_interval_s": 60})
        assert updated["polling_interval_s"] == 60
        assert updated["enabled"] is True  # Unveraendert

    def test_zigbee_default_config(self):
        engine = ZigbeeModuleEngine()
        cfg = engine.get_config()
        assert cfg["enabled"] is True
        assert cfg["lqi_threshold"] == 50

    def test_zigbee_update_config(self):
        engine = ZigbeeModuleEngine()
        updated = engine.update_config({"lqi_threshold": 30})
        assert updated["lqi_threshold"] == 30

    def test_thread_default_config(self):
        engine = ThreadModuleEngine()
        cfg = engine.get_config()
        assert cfg["enabled"] is True
        assert cfg["polling_interval_s"] == 120

    def test_thread_update_config(self):
        engine = ThreadModuleEngine()
        updated = engine.update_config({"enabled": False})
        assert updated["enabled"] is False

    def test_ha_module_default_config(self):
        engine = HomeAssistantModuleEngine()
        cfg = engine.get_config()
        assert "forwarded_domains" in cfg
        assert "light" in cfg["forwarded_domains"]
        assert cfg["webhook_retry_count"] == 3

    def test_ha_module_update_config_syncs_domains(self):
        engine = HomeAssistantModuleEngine()
        engine.update_config({"forwarded_domains": ["light", "switch"]})
        # Verify forwarded domains were synced
        status = engine.get_status()
        assert status.event_forwarding["forwarded_domains"] == ["light", "switch"]


# -- Engine update_from_ha Tests -----------------------------------------------


class TestEngineUpdates:
    """Testet update_from_ha und Datenverarbeitung."""

    def test_zwave_update_from_ha(self):
        engine = ZWaveModuleEngine()
        states = {
            "zwave_js.living_room_switch": {
                "state": "ready",
                "attributes": {"friendly_name": "Living Room Switch"},
            },
            "sensor.zwave_controller_status": {
                "state": "ready",
                "attributes": {"friendly_name": "Z-Wave Controller"},
            },
            "light.kitchen": {
                "state": "on",
                "attributes": {},
            },
        }
        engine.update_from_ha(states)
        summary = engine.get_summary()
        assert summary["device_count"] == 1  # Nur zwave_js.living_room_switch
        assert summary["controller_state"] == "ready"
        assert summary["last_update"] is not None

    def test_zigbee_update_from_ha(self):
        engine = ZigbeeModuleEngine()
        states = {
            "zha.living_room_sensor": {
                "state": "online",
                "attributes": {
                    "friendly_name": "Living Room Sensor",
                    "lqi": 85,
                },
            },
            "sensor.zigbee_coordinator": {
                "state": "online",
                "attributes": {"friendly_name": "Zigbee Coordinator"},
            },
        }
        engine.update_from_ha(states)
        summary = engine.get_summary()
        assert summary["device_count"] == 1
        assert summary["coordinator_state"] == "online"
        assert summary["avg_lqi"] == 85.0

    def test_thread_update_from_ha(self):
        engine = ThreadModuleEngine()
        states = {
            "thread.living_room_bulb": {
                "state": "online",
                "attributes": {
                    "friendly_name": "Thread Bulb",
                    "role": "router",
                },
            },
            "sensor.thread_border_router": {
                "state": "running",
                "attributes": {"friendly_name": "Thread Border Router"},
            },
        }
        engine.update_from_ha(states)
        summary = engine.get_summary()
        assert summary["device_count"] == 1
        assert summary["router_count"] == 1
        assert summary["border_router_state"] == "running"


# -- ModuleRouter Tests -------------------------------------------------------


class TestModuleRouter:
    """Testet ModuleRouter Kernfunktionalitaet."""

    def _make_router(self, tmp_path):
        return ModuleRouter(
            hub_zwave=ZWaveModuleEngine(),
            hub_zigbee=ZigbeeModuleEngine(),
            hub_thread=ThreadModuleEngine(),
            ha_module_engine=HomeAssistantModuleEngine(),
            config_path=tmp_path / "test_config.json",
        )

    def test_init_creates_default_config(self, tmp_path):
        router = self._make_router(tmp_path)
        assert (tmp_path / "test_config.json").exists()
        config = router.get_config()
        assert "zwave" in config
        assert "zigbee" in config
        assert "thread" in config
        assert "homeassistant" in config

    def test_config_persistence(self, tmp_path):
        router = self._make_router(tmp_path)
        router.update_config("zwave", {"polling_interval_s": 60})
        # Neuen Router mit gleicher Config-Datei erstellen
        router2 = ModuleRouter(config_path=tmp_path / "test_config.json")
        config = router2.get_config("zwave")
        assert config["polling_interval_s"] == 60

    def test_route_states(self, tmp_path):
        router = self._make_router(tmp_path)
        states = {
            "zwave_js.switch_1": {
                "state": "ready",
                "attributes": {"friendly_name": "Switch 1"},
            },
            "zha.sensor_1": {
                "state": "online",
                "attributes": {"friendly_name": "Zigbee Sensor", "lqi": 90},
            },
            "thread.bulb_1": {
                "state": "online",
                "attributes": {"friendly_name": "Thread Bulb"},
            },
            "light.unrelated": {
                "state": "on",
                "attributes": {},
            },
        }
        result = router.route_states(states)
        assert "zwave" in result
        assert "zigbee" in result
        assert "thread" in result
        assert "homeassistant" in result

    def test_refresh_from_states_list(self, tmp_path):
        router = self._make_router(tmp_path)
        states_list = [
            {
                "entity_id": "zwave_js.switch_1",
                "state": "ready",
                "attributes": {"friendly_name": "Switch 1"},
            },
            {
                "entity_id": "sensor.zigbee_temp",
                "state": "22.5",
                "attributes": {"friendly_name": "Zigbee Temp", "lqi": 75},
            },
        ]
        result = router.refresh_from_states_list(states_list)
        assert isinstance(result, dict)

    def test_disabled_module_skipped(self, tmp_path):
        router = self._make_router(tmp_path)
        router.update_config("zwave", {"enabled": False})
        states = {
            "zwave_js.switch_1": {
                "state": "ready",
                "attributes": {"friendly_name": "Switch 1"},
            },
        }
        result = router.route_states(states)
        assert "zwave" not in result

    def test_get_status(self, tmp_path):
        router = self._make_router(tmp_path)
        status = router.get_status()
        assert "modules" in status
        assert "zwave" in status["modules"]
        assert status["modules"]["zwave"]["available"] is True
        assert status["modules"]["zwave"]["enabled"] is True

    def test_ingest_event(self, tmp_path):
        router = self._make_router(tmp_path)
        event = {
            "type": "state_changed",
            "entity_id": "zwave_js.switch_1",
            "new": {
                "state": "ready",
                "attributes": {"friendly_name": "Switch 1"},
            },
        }
        router.ingest_event(event)
        assert "zwave_js.switch_1" in router._accumulated_states

    def test_ingest_event_ignores_non_network(self, tmp_path):
        router = self._make_router(tmp_path)
        event = {
            "type": "state_changed",
            "entity_id": "light.kitchen",
            "new": {"state": "on", "attributes": {}},
        }
        router.ingest_event(event)
        assert len(router._accumulated_states) == 0

    def test_ingest_events_batch_flushes(self, tmp_path):
        router = self._make_router(tmp_path)
        events = [
            {
                "type": "state_changed",
                "entity_id": f"zwave_js.device_{i}",
                "new": {
                    "state": "ready",
                    "attributes": {"friendly_name": f"Device {i}"},
                },
            }
            for i in range(5)
        ]
        router.ingest_events_batch(events)
        # After batch, accumulated states should be populated
        assert len(router._accumulated_states) == 5


# -- API Blueprint Tests -------------------------------------------------------


class TestNetworkModuleAPIs:
    """Testet die API-Endpoints der Netzwerk-Module."""

    def _make_app(self):
        from flask import Flask
        from copilot_core.api.v1.zwave_module import zwave_module_bp
        from copilot_core.api.v1.zigbee_module import zigbee_module_bp
        from copilot_core.api.v1.thread_module import thread_module_bp
        from copilot_core.api.v1.ha_module import ha_module_bp
        from copilot_core.api.v1.module_router_api import module_router_bp

        app = Flask(__name__)
        app.config["TESTING"] = True

        zwave = ZWaveModuleEngine()
        zigbee = ZigbeeModuleEngine()
        thread = ThreadModuleEngine()
        ha = HomeAssistantModuleEngine()
        router = ModuleRouter(
            hub_zwave=zwave,
            hub_zigbee=zigbee,
            hub_thread=thread,
            ha_module_engine=ha,
            config_path=Path("/tmp/test_module_config.json"),
        )

        app.config["COPILOT_SERVICES"] = {
            "hub_zwave": zwave,
            "hub_zigbee": zigbee,
            "hub_thread": thread,
            "ha_module_engine": ha,
            "module_router": router,
        }

        app.register_blueprint(zwave_module_bp)
        app.register_blueprint(zigbee_module_bp)
        app.register_blueprint(thread_module_bp)
        app.register_blueprint(ha_module_bp)
        app.register_blueprint(module_router_bp)

        return app

    @pytest.fixture
    def client(self):
        app = self._make_app()
        with app.test_client() as c:
            yield c

    def test_zwave_status(self, client):
        resp = client.get("/api/v1/modules/zwave/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["protocol"] == "zwave"

    def test_zwave_config(self, client):
        resp = client.get("/api/v1/modules/zwave/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "config" in data
        assert data["config"]["enabled"] is True

    def test_zwave_update_config(self, client):
        resp = client.post(
            "/api/v1/modules/zwave/config",
            json={"polling_interval_s": 60},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["config"]["polling_interval_s"] == 60

    def test_zigbee_status(self, client):
        resp = client.get("/api/v1/modules/zigbee/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_zigbee_config(self, client):
        resp = client.get("/api/v1/modules/zigbee/config")
        assert resp.status_code == 200

    def test_thread_status(self, client):
        resp = client.get("/api/v1/modules/thread/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_thread_config(self, client):
        resp = client.get("/api/v1/modules/thread/config")
        assert resp.status_code == 200

    def test_ha_module_status(self, client):
        resp = client.get("/api/v1/modules/homeassistant/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["module"] == "homeassistant"

    def test_ha_module_config_get(self, client):
        resp = client.get("/api/v1/modules/homeassistant/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "config" in data

    def test_ha_module_config_post(self, client):
        resp = client.post(
            "/api/v1/modules/homeassistant/config",
            json={"connection_timeout_s": 15},
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_router_status(self, client):
        resp = client.get("/api/v1/modules/router/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "modules" in data
        assert "zwave" in data["modules"]

    def test_router_config(self, client):
        resp = client.get("/api/v1/modules/router/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "config" in data

    def test_router_update_config(self, client):
        resp = client.post(
            "/api/v1/modules/router/config/zwave",
            json={"alert_dead_devices": False},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["module"] == "zwave"

    def test_router_update_config_invalid_module(self, client):
        resp = client.post(
            "/api/v1/modules/router/config/invalid",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400


# -- LLM Context Tests ---------------------------------------------------------


class TestLLMContext:
    """Testet LLM-Kontext-Generierung der Engines."""

    def test_zwave_context_empty(self):
        engine = ZWaveModuleEngine()
        assert engine.get_context_for_llm() == ""

    def test_zwave_context_with_data(self):
        engine = ZWaveModuleEngine()
        engine.update_from_ha({
            "zwave_js.switch": {
                "state": "ready",
                "attributes": {"friendly_name": "Switch"},
            },
        })
        ctx = engine.get_context_for_llm()
        assert "Z-Wave" in ctx
        assert "1 Geraete" in ctx

    def test_zigbee_context_empty(self):
        engine = ZigbeeModuleEngine()
        assert engine.get_context_for_llm() == ""

    def test_thread_context_empty(self):
        engine = ThreadModuleEngine()
        assert engine.get_context_for_llm() == ""

    def test_ha_context(self):
        engine = HomeAssistantModuleEngine()
        engine.update_connection_status(reachable=True, response_time_ms=42.0)
        ctx = engine.get_context_for_llm()
        assert "verbunden" in ctx
        assert "42" in ctx
