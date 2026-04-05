from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "haushalt.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security as api_security_module  # noqa: E402

spec = importlib.util.spec_from_file_location("ps_haushalt_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeWasteService:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.status_payload: object = {
            "today": ["Bio"],
            "tomorrow": ["Papier"],
            "service": "waste",
        }
        self.delivered_messages: list[str] = []

    def get_status(self):
        if self.raise_on == "get_status":
            raise RuntimeError("waste status exploded")
        return self.status_payload

    def deliver_reminder(self, message: str) -> dict[str, object]:
        if self.raise_on == "deliver_reminder":
            raise RuntimeError("waste reminder exploded")
        self.delivered_messages.append(message)
        return {"ok": True, "message": message, "service": "waste"}


class FakeBirthdayService:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.status_payload: object = {
            "today": [{"name": "Ada", "age": 37}],
            "upcoming": [
                {"name": "Linus", "days_until": 3},
                {"name": "Grace", "days_until": 10},
            ],
            "service": "birthday",
        }
        self.delivered_messages: list[str] = []

    def get_status(self):
        if self.raise_on == "get_status":
            raise RuntimeError("birthday status exploded")
        return self.status_payload

    def deliver_reminder(self, message: str) -> dict[str, object]:
        if self.raise_on == "deliver_reminder":
            raise RuntimeError("birthday reminder exploded")
        self.delivered_messages.append(message)
        return {"ok": True, "message": message, "service": "birthday"}


def _build_client(monkeypatch, *, authorized: bool = True, waste_service=None, birthday_service=None):
    monkeypatch.setattr(api_security_module, "validate_token", lambda _request: authorized)
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {
        "waste_service": waste_service,
        "birthday_service": birthday_service,
    }
    app.register_blueprint(module.haushalt_bp)
    return app.test_client()


def test_haushalt_contract_covers_overview_and_reminders(monkeypatch) -> None:
    waste_service = FakeWasteService()
    birthday_service = FakeBirthdayService()
    client = _build_client(
        monkeypatch,
        waste_service=waste_service,
        birthday_service=birthday_service,
    )
    monkeypatch.setattr(module.time, "time", lambda: 1712300000.0)

    response = client.get("/api/v1/haushalt/overview")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "last_updated": 1712300000.0,
        "alerts": {
            "waste_today": True,
            "waste_tomorrow": True,
            "birthday_today": True,
            "upcoming_birthdays_7d": 1,
        },
        "waste": waste_service.status_payload,
        "birthdays": birthday_service.status_payload,
    }

    response = client.post("/api/v1/haushalt/remind/waste")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Heute wird abgeholt: Bio.",
        "service": "waste",
    }
    assert waste_service.delivered_messages[-1] == "Heute wird abgeholt: Bio."

    waste_service.status_payload = {"today": [], "tomorrow": ["Papier"], "service": "waste"}
    response = client.post("/api/v1/haushalt/remind/waste")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Morgen wird abgeholt: Papier. Bitte Tonnen rausstellen!",
        "service": "waste",
    }

    waste_service.status_payload = {"today": [], "tomorrow": [], "service": "waste"}
    response = client.post("/api/v1/haushalt/remind/waste")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Keine Abfuhr in Sicht."}

    response = client.post("/api/v1/haushalt/remind/birthday")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "message": "Heute hat Geburtstag: Ada (wird 37). Herzlichen Glückwunsch!",
        "service": "birthday",
    }
    assert birthday_service.delivered_messages[-1] == "Heute hat Geburtstag: Ada (wird 37). Herzlichen Glückwunsch!"

    birthday_service.status_payload = {"today": [], "upcoming": [], "service": "birthday"}
    response = client.post("/api/v1/haushalt/remind/birthday")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Keine Geburtstage heute."}


def test_haushalt_contract_hardens_unavailable_and_runtime_errors(monkeypatch) -> None:
    waste_service = FakeWasteService()
    birthday_service = FakeBirthdayService()
    client = _build_client(
        monkeypatch,
        waste_service=waste_service,
        birthday_service=birthday_service,
    )

    waste_service.raise_on = "get_status"
    response = client.get("/api/v1/haushalt/overview")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "waste status exploded"}

    waste_service.raise_on = None
    waste_service.status_payload = "broken"
    response = client.post("/api/v1/haushalt/remind/waste")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "WasteCollectionService status must be an object"}

    waste_service.status_payload = {"today": ["Bio"], "tomorrow": [], "service": "waste"}
    waste_service.raise_on = "deliver_reminder"
    response = client.post("/api/v1/haushalt/remind/waste")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "waste reminder exploded"}

    birthday_service.raise_on = "get_status"
    response = client.post("/api/v1/haushalt/remind/birthday")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "birthday status exploded"}

    unavailable_client = _build_client(monkeypatch, waste_service=None, birthday_service=None)

    response = unavailable_client.get("/api/v1/haushalt/overview")
    assert response.status_code == 200
    assert response.get_json()["waste"] == {"ok": False, "error": "not initialized"}
    assert response.get_json()["birthdays"] == {"ok": False, "error": "not initialized"}

    response = unavailable_client.post("/api/v1/haushalt/remind/waste")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "WasteCollectionService not available"}

    response = unavailable_client.post("/api/v1/haushalt/remind/birthday")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "BirthdayService not available"}


def test_haushalt_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(
        monkeypatch,
        authorized=False,
        waste_service=FakeWasteService(),
        birthday_service=FakeBirthdayService(),
    )

    response = client.get("/api/v1/haushalt/overview")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
