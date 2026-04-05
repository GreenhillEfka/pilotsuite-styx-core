from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security  # noqa: E402
from copilot_core.api.v1 import shopping as module  # noqa: E402


def _build_client(monkeypatch, tmp_path, *, authorized: bool = True):
    db_path = tmp_path / "shopping_contract.sqlite3"
    if db_path.exists():
        db_path.unlink()

    monkeypatch.setattr(module, "DB_PATH", str(db_path))
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)

    os.makedirs(tmp_path, exist_ok=True)
    module._init_db()

    app = Flask(__name__)
    app.register_blueprint(module.shopping_bp)
    return app.test_client(), db_path


def test_shopping_contract_covers_shopping_and_reminder_routes(monkeypatch, tmp_path) -> None:
    client, _db_path = _build_client(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/shopping",
        json={"name": "Milch", "quantity": "2", "category": "kuehlregal"},
    )
    assert response.status_code == 201
    shopping_single = response.get_json()
    assert shopping_single["success"] is True
    assert shopping_single["count"] == 1
    milk_id = shopping_single["added"][0]["id"]

    response = client.post(
        "/api/v1/shopping",
        json={"items": [{"name": "Brot"}, {"name": "Eier", "quantity": "12"}]},
    )
    assert response.status_code == 201
    shopping_batch = response.get_json()
    assert shopping_batch == {
        "success": True,
        "added": shopping_batch["added"],
        "count": 2,
    }
    bread_id = shopping_batch["added"][0]["id"]
    eggs_id = shopping_batch["added"][1]["id"]

    response = client.get("/api/v1/shopping")
    assert response.status_code == 200
    shopping_list = response.get_json()
    assert shopping_list["count"] == 3
    assert [item["name"] for item in shopping_list["items"]] == ["Eier", "Brot", "Milch"]

    response = client.post(f"/api/v1/shopping/{milk_id}/complete")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "id": milk_id}

    response = client.get("/api/v1/shopping?completed=1")
    assert response.status_code == 200
    assert response.get_json() == {
        "items": [
            {
                "id": milk_id,
                "name": "Milch",
                "quantity": "2",
                "category": "kuehlregal",
                "completed": 1,
                "created_at": response.get_json()["items"][0]["created_at"],
                "completed_at": response.get_json()["items"][0]["completed_at"],
            }
        ],
        "count": 1,
    }

    response = client.post("/api/v1/shopping/clear-completed")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "deleted": 1}

    response = client.delete(f"/api/v1/shopping/{bread_id}")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "deleted": bread_id}

    response = client.get("/api/v1/shopping?completed=0")
    assert response.status_code == 200
    assert response.get_json()["items"] == [
        {
            "id": eggs_id,
            "name": "Eier",
            "quantity": "12",
            "category": "",
            "completed": 0,
            "created_at": response.get_json()["items"][0]["created_at"],
            "completed_at": None,
        }
    ]

    response = client.post(
        "/api/v1/reminders",
        json={
            "title": "Rechnung zahlen",
            "description": "Strom",
            "due_at": "2026-04-04T17:30:00Z",
            "recurring": "monthly",
        },
    )
    assert response.status_code == 201
    reminder_due = response.get_json()
    assert reminder_due["success"] is True
    due_id = reminder_due["id"]

    response = client.post("/api/v1/reminders", json={"title": "Muell rausbringen"})
    assert response.status_code == 201
    reminder_open = response.get_json()
    assert reminder_open["success"] is True
    open_id = reminder_open["id"]

    response = client.get("/api/v1/reminders")
    assert response.status_code == 200
    reminders = response.get_json()
    assert reminders["count"] == 2
    assert [item["title"] for item in reminders["reminders"]] == ["Rechnung zahlen", "Muell rausbringen"]

    response = client.get("/api/v1/reminders?due=1")
    assert response.status_code == 200
    due_only = response.get_json()
    assert due_only["count"] == 1
    assert due_only["reminders"][0]["id"] == due_id
    assert due_only["reminders"][0]["title"] == "Rechnung zahlen"

    response = client.post(f"/api/v1/reminders/{due_id}/snooze", json={"minutes": 15})
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "id": due_id, "snoozed_minutes": 15}

    response = client.get("/api/v1/reminders?due=1")
    assert response.status_code == 200
    assert response.get_json() == {"reminders": [], "count": 0}

    response = client.post(f"/api/v1/reminders/{open_id}/complete")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "id": open_id}

    response = client.get("/api/v1/reminders?completed=1")
    assert response.status_code == 200
    completed = response.get_json()
    assert completed["count"] == 1
    assert completed["reminders"][0]["id"] == open_id
    assert completed["reminders"][0]["title"] == "Muell rausbringen"

    response = client.delete(f"/api/v1/reminders/{due_id}")
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "deleted": due_id}


def test_shopping_contract_hardens_validation_and_not_found_paths(monkeypatch, tmp_path) -> None:
    client, _db_path = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/v1/shopping?completed=2")
    assert response.status_code == 400
    assert response.get_json() == {"error": "completed must be 0 or 1"}

    response = client.post("/api/v1/shopping")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body required"}

    response = client.post("/api/v1/shopping", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/shopping", json={"items": {"name": "Milch"}})
    assert response.status_code == 400
    assert response.get_json() == {"error": "items must be a list"}

    response = client.post("/api/v1/shopping", json={"items": ["bad"]})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Each item must be an object"}

    response = client.post("/api/v1/shopping", json={"items": [{"name": "   "}]})
    assert response.status_code == 400
    assert response.get_json() == {"error": "At least one item with a name is required"}

    response = client.post("/api/v1/shopping/missing/complete")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Item not found"}

    response = client.delete("/api/v1/shopping/missing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Item not found"}

    response = client.get("/api/v1/reminders?completed=3")
    assert response.status_code == 400
    assert response.get_json() == {"error": "completed must be 0 or 1"}

    response = client.get("/api/v1/reminders?due=2")
    assert response.status_code == 400
    assert response.get_json() == {"error": "due must be 0 or 1"}

    response = client.post("/api/v1/reminders")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body required"}

    response = client.post("/api/v1/reminders", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/reminders", json={"title": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}

    response = client.post("/api/v1/reminders", json={"title": "Rechnung", "due_at": {"bad": True}})
    assert response.status_code == 400
    assert response.get_json() == {"error": "due_at must be epoch seconds or ISO-8601"}

    response = client.post("/api/v1/reminders/missing/snooze", json=["bad"])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/reminders/missing/snooze", json={"minutes": "x"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "minutes must be an integer"}

    response = client.post("/api/v1/reminders/missing/complete")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Reminder not found"}

    response = client.post("/api/v1/reminders/missing/snooze")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Reminder not found or already completed"}

    response = client.delete("/api/v1/reminders/missing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Reminder not found"}


def test_shopping_contract_requires_authentication(monkeypatch, tmp_path) -> None:
    client, _db_path = _build_client(monkeypatch, tmp_path, authorized=False)

    response = client.get("/api/v1/shopping")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


def test_shopping_contract_returns_json_500_for_storage_runtime_errors(monkeypatch, tmp_path) -> None:
    client, _db_path = _build_client(monkeypatch, tmp_path)

    def explode():
        raise RuntimeError("shopping exploded")

    monkeypatch.setattr(module, "_get_conn", explode)

    response = client.get("/api/v1/shopping")
    assert response.status_code == 500
    assert response.get_json() == {"error": "shopping exploded"}

    response = client.post("/api/v1/reminders", json={"title": "Rechnung"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "shopping exploded"}
