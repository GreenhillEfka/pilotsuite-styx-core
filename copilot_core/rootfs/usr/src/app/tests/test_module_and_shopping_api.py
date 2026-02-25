"""Regression tests for module settings and shopping/reminder APIs."""

from __future__ import annotations

import tempfile

from flask import Flask


def _create_api_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True

    from copilot_core.api.v1.module_control import module_control_bp, init_module_control_api
    from copilot_core.api.v1.shopping import shopping_bp
    from copilot_core.module_registry import ModuleRegistry

    init_module_control_api(ModuleRegistry.get_instance())
    app.register_blueprint(module_control_bp)
    app.register_blueprint(shopping_bp)
    return app


def _reset_module_registry(db_path: str) -> None:
    import copilot_core.module_registry as module_registry

    module_registry.DB_PATH = db_path
    module_registry.ModuleRegistry._reset_instance()


def _reset_shopping_db(db_path: str) -> None:
    import copilot_core.api.v1.shopping as shopping

    shopping._DB_PATH = db_path
    shopping._db_initialized_for = None


def test_module_settings_roundtrip(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")

    with tempfile.TemporaryDirectory() as tmpdir:
        _reset_module_registry(f"{tmpdir}/module_states.db")
        app = _create_api_app()
        client = app.test_client()

        resp = client.get("/api/v1/modules/habitus_miner/settings")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is True
        assert payload["state"] == "active"
        assert payload["settings"] == {}

        resp = client.post(
            "/api/v1/modules/habitus_miner/settings",
            json={"settings": {"auto_apply_threshold": 0.73, "notes": "test"}},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["settings"]["auto_apply_threshold"] == 0.73

        resp = client.post(
            "/api/v1/modules/habitus_miner/configure",
            json={"state": "learning"},
        )
        assert resp.status_code == 200

        resp = client.get("/api/v1/modules/habitus_miner/settings")
        payload = resp.get_json()
        assert payload["state"] == "learning"
        assert payload["settings"]["notes"] == "test"


def test_module_catalog_and_presets(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")

    with tempfile.TemporaryDirectory() as tmpdir:
        _reset_module_registry(f"{tmpdir}/module_states.db")
        app = _create_api_app()
        client = app.test_client()

        catalog = client.get("/api/v1/modules/catalog")
        assert catalog.status_code == 200
        catalog_data = catalog.get_json()
        assert catalog_data["ok"] is True
        assert isinstance(catalog_data["modules"], list)
        assert any(m["id"] == "habitus_miner" for m in catalog_data["modules"])

        presets = client.get("/api/v1/modules/presets")
        assert presets.status_code == 200
        presets_data = presets.get_json()
        assert presets_data["ok"] is True
        assert presets_data["count"] >= 1
        assert any(p["id"] == "balanced_home" for p in presets_data["presets"])

        dry_run = client.post(
            "/api/v1/modules/presets/apply",
            json={"preset_id": "balanced_home", "dry_run": True},
        )
        assert dry_run.status_code == 200
        dry_data = dry_run.get_json()
        assert dry_data["ok"] is True
        assert dry_data["dry_run"] is True
        assert "brain_graph" in dry_data["state_changes"]


def test_module_preset_apply_updates_states(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")

    with tempfile.TemporaryDirectory() as tmpdir:
        _reset_module_registry(f"{tmpdir}/module_states.db")
        app = _create_api_app()
        client = app.test_client()

        applied = client.post(
            "/api/v1/modules/presets/apply",
            json={"preset_id": "balanced_home"},
        )
        assert applied.status_code in (200, 207)
        payload = applied.get_json()
        assert payload["ok"] is True
        assert payload["applied_states"]["brain_graph"] == "active"
        assert payload["applied_states"]["habitus_miner"] in {"learning", "active"}

        brain_state = client.get("/api/v1/modules/brain_graph")
        assert brain_state.status_code == 200
        assert brain_state.get_json()["state"] == "active"

        habitus_state = client.get("/api/v1/modules/habitus_miner")
        assert habitus_state.status_code == 200
        assert habitus_state.get_json()["state"] in {"learning", "active"}


def test_shopping_and_reminder_flow(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")

    with tempfile.TemporaryDirectory() as tmpdir:
        _reset_shopping_db(f"{tmpdir}/shopping.db")
        app = _create_api_app()
        client = app.test_client()

        add_item = client.post(
            "/api/v1/shopping",
            json={"name": "Milch", "quantity": "2"},
        )
        assert add_item.status_code == 200
        item_id = add_item.get_json()["id"]

        listed = client.get("/api/v1/shopping?limit=invalid")
        assert listed.status_code == 200
        items = listed.get_json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Milch"

        done = client.post(f"/api/v1/shopping/{item_id}/complete")
        assert done.status_code == 200
        assert done.get_json()["ok"] is True

        reopened = client.post(f"/api/v1/shopping/{item_id}/reopen")
        assert reopened.status_code == 200
        assert reopened.get_json()["ok"] is True

        deleted = client.delete(f"/api/v1/shopping/{item_id}")
        assert deleted.status_code == 200
        assert deleted.get_json()["ok"] is True

        add_reminder = client.post(
            "/api/v1/reminders",
            json={
                "title": "Waschmaschine",
                "due_in_minutes": 10,
                "trigger_reason": "motion-laundry",
            },
        )
        assert add_reminder.status_code == 200
        reminder_id = add_reminder.get_json()["id"]

        reminders = client.get("/api/v1/reminders?include_events=1&limit=invalid")
        assert reminders.status_code == 200
        payload = reminders.get_json()
        assert payload["count"] == 1
        reminder = payload["reminders"][0]
        assert reminder["id"] == reminder_id
        assert reminder["status_reason"] in {"scheduled", "open"}
        assert isinstance(reminder.get("events", []), list)

        snooze = client.post(
            f"/api/v1/reminders/{reminder_id}/snooze",
            json={"minutes": "invalid"},
        )
        assert snooze.status_code == 200
        assert snooze.get_json()["ok"] is True

        explain = client.get("/api/v1/reminders/explain?limit=oops")
        assert explain.status_code == 200
        assert explain.get_json()["ok"] is True
