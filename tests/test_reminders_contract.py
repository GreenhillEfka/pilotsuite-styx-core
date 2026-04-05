from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security  # noqa: E402
from copilot_core.api.v1 import reminders as module  # noqa: E402


class FakeWasteService:
    def __init__(self) -> None:
        self.updated_events: list[dict[str, object]] = []
        self.updated_collections: list[list[object]] = []
        self.delivered: list[tuple[str, str]] = []
        self.status_payload = {"today": ["Bio"], "tomorrow": ["Papier"], "service": "waste"}
        self.raise_on: str | None = None

    def update_from_ha(self, data: dict[str, object]) -> dict[str, object]:
        if self.raise_on == "update_from_ha":
            raise RuntimeError("waste event exploded")
        self.updated_events.append(data)
        return {"ok": True, "kind": "waste_event", "received": data}

    def update_collections(self, collections: list[object]) -> dict[str, object]:
        if self.raise_on == "update_collections":
            raise RuntimeError("waste collections exploded")
        self.updated_collections.append(collections)
        return {"ok": True, "updated": len(collections)}

    def get_status(self) -> dict[str, object]:
        if self.raise_on == "get_status":
            raise RuntimeError("waste status exploded")
        return self.status_payload

    def deliver_reminder(self, message: str, tts_entity: str) -> dict[str, object]:
        if self.raise_on == "deliver_reminder":
            raise RuntimeError("waste reminder exploded")
        self.delivered.append((message, tts_entity))
        return {"ok": True, "message": message, "tts_entity": tts_entity}


class FakeBirthdayService:
    def __init__(self) -> None:
        self.updated_birthdays: list[list[object]] = []
        self.delivered: list[tuple[str, str]] = []
        self.status_payload = {"today": [{"name": "Ada"}], "service": "birthday"}
        self.raise_on: str | None = None

    def update_birthdays(self, birthdays: list[object]) -> dict[str, object]:
        if self.raise_on == "update_birthdays":
            raise RuntimeError("birthday update exploded")
        self.updated_birthdays.append(birthdays)
        return {"ok": True, "updated": len(birthdays)}

    def get_status(self) -> dict[str, object]:
        if self.raise_on == "get_status":
            raise RuntimeError("birthday status exploded")
        return self.status_payload

    def deliver_reminder(self, message: str, tts_entity: str) -> dict[str, object]:
        if self.raise_on == "deliver_reminder":
            raise RuntimeError("birthday reminder exploded")
        self.delivered.append((message, tts_entity))
        return {"ok": True, "message": message, "tts_entity": tts_entity}


def _build_client(monkeypatch, *, authorized: bool = True, waste_service=None, birthday_service=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    module.init_reminders_api(waste_service=waste_service, birthday_service=birthday_service)
    app = Flask(__name__)
    app.register_blueprint(module.reminders_bp)
    return app.test_client()


def test_reminders_contract_covers_waste_and_birthday_surfaces(monkeypatch) -> None:
    waste_service = FakeWasteService()
    birthday_service = FakeBirthdayService()
    client = _build_client(monkeypatch, waste_service=waste_service, birthday_service=birthday_service)

    response = client.post("/api/v1/waste/event", json={"source": "ha", "kind": "pickup"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "kind": "waste_event", "received": {"source": "ha", "kind": "pickup"}}
    assert waste_service.updated_events == [{"source": "ha", "kind": "pickup"}]

    response = client.post("/api/v1/waste/collections", json={"collections": [{"date": "2026-04-05", "type": "Bio"}]})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "updated": 1}
    assert waste_service.updated_collections == [[{"date": "2026-04-05", "type": "Bio"}]]

    response = client.get("/api/v1/waste/status")
    assert response.status_code == 200
    assert response.get_json() == {"today": ["Bio"], "tomorrow": ["Papier"], "service": "waste"}

    response = client.post("/api/v1/waste/remind", json={"message": "Bitte Muell rausbringen", "tts_entity": "media_player.kitchen"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Bitte Muell rausbringen", "tts_entity": "media_player.kitchen"}
    assert waste_service.delivered[-1] == ("Bitte Muell rausbringen", "media_player.kitchen")

    waste_service.status_payload = {"today": [], "tomorrow": ["Papier"], "service": "waste"}
    response = client.post("/api/v1/waste/remind", json={})
    assert response.status_code == 200
    auto_waste = response.get_json()
    assert auto_waste["ok"] is True
    assert auto_waste["message"] == "Morgen wird abgeholt: Papier. Bitte Tonnen rausstellen!"

    response = client.post("/api/v1/birthday/update", json={"birthdays": [{"name": "Ada", "date": "2026-04-04"}]})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "updated": 1}
    assert birthday_service.updated_birthdays == [[{"name": "Ada", "date": "2026-04-04"}]]

    response = client.get("/api/v1/birthday/status")
    assert response.status_code == 200
    assert response.get_json() == {"today": [{"name": "Ada"}], "service": "birthday"}

    response = client.post("/api/v1/birthday/remind", json={"message": "Ada hat Geburtstag", "tts_entity": "media_player.office"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Ada hat Geburtstag", "tts_entity": "media_player.office"}
    assert birthday_service.delivered[-1] == ("Ada hat Geburtstag", "media_player.office")

    birthday_service.status_payload = {"today": [{"name": "Ada"}], "service": "birthday"}
    response = client.post("/api/v1/birthday/remind", json={})
    assert response.status_code == 200
    auto_birthday = response.get_json()
    assert auto_birthday["ok"] is True
    assert auto_birthday["message"] == "Heute hat Geburtstag: Ada. Herzlichen Glückwunsch!"


def test_reminders_contract_hardens_validation_unavailable_and_runtime_errors(monkeypatch) -> None:
    waste_service = FakeWasteService()
    birthday_service = FakeBirthdayService()
    client = _build_client(monkeypatch, waste_service=waste_service, birthday_service=birthday_service)

    response = client.post("/api/v1/waste/event")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/waste/event", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/waste/collections", json={"collections": {"date": "2026-04-05"}})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "collections must be a list"}

    response = client.post("/api/v1/waste/remind", json={"message": 1})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "message must be a string"}

    response = client.post("/api/v1/waste/remind", json={"tts_entity": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "tts_entity must be a string"}

    waste_service.status_payload = {"today": [], "tomorrow": [], "service": "waste"}
    response = client.post("/api/v1/waste/remind", json={})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Keine Abfuhr in Sicht."}

    response = client.post("/api/v1/birthday/update")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/birthday/update", json={"birthdays": {"name": "Ada"}})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "birthdays must be a list"}

    response = client.post("/api/v1/birthday/remind", json={"message": ["bad"]})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "message must be a string"}

    response = client.post("/api/v1/birthday/remind", json={"tts_entity": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "tts_entity must be a string"}

    birthday_service.status_payload = {"today": [], "service": "birthday"}
    response = client.post("/api/v1/birthday/remind", json={})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Keine Geburtstage heute."}

    waste_service.raise_on = "update_from_ha"
    response = client.post("/api/v1/waste/event", json={"source": "ha"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "waste event exploded"}

    waste_service.raise_on = "get_status"
    response = client.get("/api/v1/waste/status")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "waste status exploded"}

    birthday_service.raise_on = "deliver_reminder"
    response = client.post("/api/v1/birthday/remind", json={"message": "Ada"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "birthday reminder exploded"}

    unavailable_client = _build_client(monkeypatch, waste_service=None, birthday_service=None)

    response = unavailable_client.post("/api/v1/waste/event", json={"source": "ha"})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "WasteCollectionService not available"}

    response = unavailable_client.get("/api/v1/birthday/status")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "BirthdayService not available"}


def test_reminders_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, waste_service=FakeWasteService(), birthday_service=FakeBirthdayService())

    response = client.get("/api/v1/waste/status")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
