from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.security import get_auth_token  # noqa: E402
from copilot_core.api.v1 import alarm as module  # noqa: E402
from copilot_core.alarm import curves as alarm_curves_module  # noqa: E402


class FakeConfig:
    def __init__(self, alarm_id: str, *, name: str = "Morgenroutine", zone_id: str = "sleep") -> None:
        self.alarm_id = alarm_id
        self.name = name
        self.zone_id = zone_id

    def to_dict(self) -> dict[str, object]:
        return {
            "alarm_id": self.alarm_id,
            "name": self.name,
            "zone_id": self.zone_id,
            "schedule": {"time": "07:00", "days": ["mon"], "enabled": True, "one_shot": False, "timezone": "Europe/Berlin"},
            "light": {"entity_ids": ["light.bedroom"], "curve_type": "quadratic"},
            "music": {"source_type": "favorite", "source_name": "Morning Mix", "enabled": True},
            "snooze_minutes": 9,
        }


class FakeAlarmEngine:
    def __init__(self) -> None:
        self.created_payloads: list[dict[str, object]] = []
        self.updated_payloads: list[tuple[str, dict[str, object]]] = []
        self.created_from_preset_payloads: list[tuple[str, dict[str, object]]] = []
        self.deleted_alarm_ids: list[str] = []
        self.deleted_preset_ids: list[str] = []

    def get_dashboard(self) -> dict[str, object]:
        return {
            "alarms": [{"alarm_id": "wake-1", "name": "Morgenroutine"}],
            "presets": [{"preset_id": "gentle-rise", "label": "Gentle Rise"}],
            "curve_types": ["quadratic", "sigmoid"],
        }

    def list_alarms(self) -> list[dict[str, object]]:
        return [
            {
                **FakeConfig("wake-1").to_dict(),
                "runtime": {"state": "armed", "next_trigger": "2026-04-05T07:00:00+02:00"},
            }
        ]

    def create_alarm(self, data: dict[str, object]) -> FakeConfig:
        self.created_payloads.append(data)
        return FakeConfig(str(data.get("alarm_id") or "wake-2"), name=str(data.get("name") or "Neuer Alarm"))

    def get_alarm(self, alarm_id: str) -> dict[str, object] | None:
        if alarm_id == "missing":
            return None
        return {
            **FakeConfig(alarm_id).to_dict(),
            "runtime": {"state": "armed", "snooze_count": 0},
        }

    def update_alarm(self, alarm_id: str, data: dict[str, object]) -> FakeConfig | None:
        if alarm_id == "missing":
            return None
        self.updated_payloads.append((alarm_id, data))
        return FakeConfig(alarm_id, name=str(data.get("name") or "Aktualisiert"))

    def delete_alarm(self, alarm_id: str) -> bool:
        if alarm_id == "missing":
            return False
        self.deleted_alarm_ids.append(alarm_id)
        return True

    def trigger_alarm(self, alarm_id: str) -> dict[str, object] | None:
        if alarm_id == "missing":
            return None
        return {"alarm_id": alarm_id, "action": "triggered", "mode": "wake"}

    def snooze_alarm(self, alarm_id: str) -> dict[str, object] | None:
        if alarm_id == "missing":
            return None
        return {"alarm_id": alarm_id, "action": "snoozed", "snooze_minutes": 9, "snooze_count": 1}

    def cancel_alarm(self, alarm_id: str) -> dict[str, object] | None:
        if alarm_id == "missing":
            return None
        return {"alarm_id": alarm_id, "action": "cancelled"}

    def get_alarms_for_zone(self, zone_id: str) -> list[dict[str, object]]:
        return [{"alarm_id": f"{zone_id}-wake", "zone_id": zone_id, "name": "Zonenalarm"}]

    def list_presets(self) -> list[dict[str, object]]:
        return [{"preset_id": "gentle-rise", "label": "Gentle Rise"}]

    def get_preset(self, preset_id: str) -> dict[str, object] | None:
        if preset_id == "missing":
            return None
        return {"preset_id": preset_id, "label": "Gentle Rise", "mode": "wake"}

    def delete_preset(self, preset_id: str) -> bool:
        if preset_id == "missing":
            return False
        self.deleted_preset_ids.append(preset_id)
        return True

    def create_from_preset(self, preset_id: str, overrides: dict[str, object]) -> FakeConfig | None:
        if preset_id == "missing":
            return None
        self.created_from_preset_payloads.append((preset_id, overrides))
        return FakeConfig("wake-from-preset", name=str(overrides.get("name") or "Preset Alarm"))


def _build_client(monkeypatch, engine: FakeAlarmEngine | None = None):
    monkeypatch.setattr(module, "_engine", engine)
    app = Flask(__name__)
    app.register_blueprint(module.alarm_bp)
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {get_auth_token()}"
    return client


def test_alarm_contract_covers_dashboard_crud_runtime_and_zone_surfaces(monkeypatch) -> None:
    engine = FakeAlarmEngine()
    client = _build_client(monkeypatch, engine)

    response = client.get("/api/v1/alarm/dashboard")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "alarms": [{"alarm_id": "wake-1", "name": "Morgenroutine"}],
        "presets": [{"preset_id": "gentle-rise", "label": "Gentle Rise"}],
        "curve_types": ["quadratic", "sigmoid"],
    }

    response = client.get("/api/v1/alarm/alarms")
    assert response.status_code == 200
    alarms = response.get_json()
    assert alarms["ok"] is True
    assert alarms["alarms"][0]["alarm_id"] == "wake-1"
    assert alarms["alarms"][0]["runtime"]["state"] == "armed"

    response = client.post(
        "/api/v1/alarm/alarms",
        json={"alarm_id": "wake-created", "name": "Frühschicht", "zone_id": "office"},
    )
    assert response.status_code == 201
    assert response.get_json()["alarm"]["alarm_id"] == "wake-created"
    assert engine.created_payloads == [{"alarm_id": "wake-created", "name": "Frühschicht", "zone_id": "office"}]

    response = client.get("/api/v1/alarm/alarms/wake-1")
    assert response.status_code == 200
    assert response.get_json()["alarm"]["runtime"] == {"state": "armed", "snooze_count": 0}

    response = client.put("/api/v1/alarm/alarms/wake-1", json={"name": "Spätschicht"})
    assert response.status_code == 200
    assert response.get_json()["alarm"]["name"] == "Spätschicht"
    assert engine.updated_payloads == [("wake-1", {"name": "Spätschicht"})]

    response = client.delete("/api/v1/alarm/alarms/wake-1")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "deleted": "wake-1"}
    assert engine.deleted_alarm_ids == ["wake-1"]

    response = client.post("/api/v1/alarm/alarms/wake-1/trigger")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "alarm_id": "wake-1", "action": "triggered", "mode": "wake"}

    response = client.post("/api/v1/alarm/alarms/wake-1/snooze")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "alarm_id": "wake-1",
        "action": "snoozed",
        "snooze_minutes": 9,
        "snooze_count": 1,
    }

    response = client.post("/api/v1/alarm/alarms/wake-1/cancel")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "alarm_id": "wake-1", "action": "cancelled"}

    response = client.get("/api/v1/alarm/zones/sleep/alarms")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "sleep",
        "alarms": [{"alarm_id": "sleep-wake", "zone_id": "sleep", "name": "Zonenalarm"}],
    }


def test_alarm_contract_covers_presets_curves_and_not_found_paths(monkeypatch) -> None:
    engine = FakeAlarmEngine()
    client = _build_client(monkeypatch, engine)

    response = client.get("/api/v1/alarm/presets")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "presets": [{"preset_id": "gentle-rise", "label": "Gentle Rise"}],
    }

    response = client.get("/api/v1/alarm/presets/gentle-rise")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "preset": {"preset_id": "gentle-rise", "label": "Gentle Rise", "mode": "wake"},
    }

    response = client.delete("/api/v1/alarm/presets/gentle-rise")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "deleted": "gentle-rise"}
    assert engine.deleted_preset_ids == ["gentle-rise"]

    response = client.post("/api/v1/alarm/presets/gentle-rise/create-alarm", json={"name": "Preset Start"})
    assert response.status_code == 201
    assert response.get_json()["alarm"]["alarm_id"] == "wake-from-preset"
    assert engine.created_from_preset_payloads == [("gentle-rise", {"name": "Preset Start"})]

    monkeypatch.setattr(
        alarm_curves_module,
        "get_all_curves",
        lambda: [{"type": "quadratic", "description": "Weber-Fechner", "samples": [0.0, 1.0]}],
    )
    response = client.get("/api/v1/alarm/curves")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "curves": [{"type": "quadratic", "description": "Weber-Fechner", "samples": [0.0, 1.0]}],
    }

    response = client.get("/api/v1/alarm/alarms/missing")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Alarm not found"}

    response = client.put("/api/v1/alarm/alarms/missing", json={"name": "Unbekannt"})
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Alarm not found"}

    response = client.delete("/api/v1/alarm/alarms/missing")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Alarm not found"}

    response = client.post("/api/v1/alarm/alarms/missing/trigger")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Alarm not found"}

    response = client.post("/api/v1/alarm/alarms/missing/snooze")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Alarm not found"}

    response = client.post("/api/v1/alarm/alarms/missing/cancel")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Alarm not found"}

    response = client.get("/api/v1/alarm/presets/missing")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Preset not found"}

    response = client.delete("/api/v1/alarm/presets/missing")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Preset not found"}

    response = client.post("/api/v1/alarm/presets/missing/create-alarm", json={"name": "Nope"})
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Preset not found"}


def test_alarm_contract_hardens_missing_engine_and_json_validation(monkeypatch) -> None:
    client = _build_client(monkeypatch, None)

    response = client.get("/api/v1/alarm/dashboard")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "Alarm engine not initialized"}

    response = client.post("/api/v1/alarm/alarms")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "Alarm engine not initialized"}

    response = client.post("/api/v1/alarm/presets/gentle-rise/create-alarm")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "Alarm engine not initialized"}

    engine = FakeAlarmEngine()
    client = _build_client(monkeypatch, engine)

    response = client.post("/api/v1/alarm/alarms")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/alarm/alarms", json=["not", "an", "object"])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.put("/api/v1/alarm/alarms/wake-1", json=["not", "an", "object"])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/alarm/presets/gentle-rise/create-alarm", json=["not", "an", "object"])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}


def test_alarm_contract_returns_json_500_for_engine_runtime_errors(monkeypatch) -> None:
    engine = FakeAlarmEngine()
    client = _build_client(monkeypatch, engine)

    def explode() -> None:
        raise RuntimeError("alarm exploded")

    def explode_with_alarm(_alarm_id: str) -> None:
        raise RuntimeError("alarm exploded")

    def explode_with_preset(_preset_id: str, _overrides: dict[str, object]) -> None:
        raise RuntimeError("alarm exploded")

    monkeypatch.setattr(engine, "list_alarms", explode)
    response = client.get("/api/v1/alarm/alarms")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "alarm exploded"}

    monkeypatch.setattr(engine, "trigger_alarm", explode_with_alarm)
    response = client.post("/api/v1/alarm/alarms/wake-1/trigger")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "alarm exploded"}

    monkeypatch.setattr(engine, "create_from_preset", explode_with_preset)
    response = client.post("/api/v1/alarm/presets/gentle-rise/create-alarm", json={"name": "Boom"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "alarm exploded"}
