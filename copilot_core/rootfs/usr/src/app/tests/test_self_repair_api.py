"""Tests for /api/v1/self-repair endpoints."""

from __future__ import annotations

from flask import Flask

from copilot_core.api.v1 import self_repair


def _build_app() -> Flask:
    app = Flask("self_repair_test")
    app.config["COPILOT_SERVICES"] = {}
    app.register_blueprint(self_repair.self_repair_bp)
    return app


def test_self_repair_status_endpoint(monkeypatch):
    monkeypatch.setattr(self_repair, "_load_settings", lambda: {"enabled": True, "github": {"token": "abc"}})
    monkeypatch.setattr(
        self_repair,
        "_build_self_check",
        lambda limit=10, force=False: {
            "ok": True,
            "integrity": {"status": "degraded", "score": 72, "color": "orange"},
            "repo": {"active_channel": "official"},
            "llm": {"ok": True, "status": {"primary_provider": "offline"}},
            "errors": [{"id": "err_1", "message": "test"}],
        },
    )
    monkeypatch.setattr(self_repair, "_load_jobs", lambda: [])

    app = _build_app()
    client = app.test_client()

    response = client.get("/api/v1/self-repair/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["integrity"]["status"] == "degraded"
    assert payload["errors_preview"][0]["id"] == "err_1"


def test_self_repair_errors_endpoint(monkeypatch):
    monkeypatch.setattr(
        self_repair,
        "_collect_error_events",
        lambda limit=10, include_warnings=True: [
            {
                "id": "err_async",
                "level": "ERROR",
                "module": "camera_context",
                "message": "coroutine was never awaited",
                "category": "async-await",
                "fixability": "high",
                "hint": "await task",
                "time": "2026-02-26T00:00:00+00:00",
            }
        ],
    )

    app = _build_app()
    client = app.test_client()

    response = client.get("/api/v1/self-repair/errors?limit=5")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["errors"][0]["category"] == "async-await"


def test_create_self_repair_job(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        self_repair,
        "_load_settings",
        lambda: {
            "enabled": True,
            "repair_mode": "advisory",
            "repair_provider": "auto",
            "max_errors_per_job": 6,
            "source_channel": "official",
            "github": {
                "enabled": False,
                "token": "",
                "repo_owner": "",
                "repo_name": "",
                "working_branch": "styx-self-repair",
                "allow_push": False,
                "allow_upstream_pr": False,
            },
            "official_repo": {
                "owner": "GreenhillEfka",
                "name": "pilotsuite-styx-core",
                "default_branch": "main",
            },
        },
    )
    monkeypatch.setattr(
        self_repair,
        "_collect_error_events",
        lambda limit=10, include_warnings=True: [
            {
                "id": "err_123",
                "level": "ERROR",
                "module": "runtime",
                "message": "module setup failed",
                "category": "runtime",
                "fixability": "medium",
                "hint": "check module context",
                "time": "2026-02-26T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(self_repair, "_build_integrity_snapshot", lambda force=False: {"status": "degraded", "score": 70})
    monkeypatch.setattr(
        self_repair,
        "_llm_snapshot",
        lambda force_refresh=False: {"ok": True, "status": {"primary_provider": "offline"}},
    )
    monkeypatch.setattr(
        self_repair,
        "_repo_snapshot",
        lambda settings: {"active_channel": "official", "official_repo": "GreenhillEfka/pilotsuite-styx-core"},
    )
    monkeypatch.setattr(
        self_repair,
        "_prepare_workspace_branch",
        lambda settings, force_sync=False, branch_hint="": {
            "ok": True,
            "workspace": {
                "repo_path": "/tmp/workspace/repo",
                "working_branch": "styx-self-repair-test",
                "head": "abc1234",
            },
        },
    )
    monkeypatch.setattr(
        self_repair,
        "_generate_repair_plan",
        lambda **kwargs: {
            "provider_result": {"provider": "ollama", "content": "ok"},
            "model_selector": "primary",
            "plan": {"diagnosis": "ok", "actions": [{"type": "manual_review"}]},
            "raw_content": "{\"diagnosis\":\"ok\"}",
        },
    )

    def _capture(job: dict):
        captured["job"] = job

    monkeypatch.setattr(self_repair, "_append_job", _capture)

    app = _build_app()
    client = app.test_client()
    response = client.post("/api/v1/self-repair/jobs", json={"error_ids": ["err_123"]})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    job = payload["job"]
    assert job["status"] == "completed"
    assert job["llm"]["provider"] == "ollama"
    assert job["plan"]["diagnosis"] == "ok"
    assert job["workspace"]["working_branch"] == "styx-self-repair-test"
    assert captured["job"]["id"] == job["id"]


def test_workspace_prepare_endpoint(monkeypatch):
    monkeypatch.setattr(
        self_repair,
        "_load_settings",
        lambda: {
            "enabled": True,
            "source_channel": "official",
            "official_repo": {"owner": "GreenhillEfka", "name": "pilotsuite-styx-core", "default_branch": "main"},
            "github": {"token": "", "repo_owner": "", "repo_name": "", "default_branch": "main"},
            "workspace": {"enabled": True, "root_path": "/tmp/ws", "sync_on_job": True},
        },
    )
    monkeypatch.setattr(
        self_repair,
        "_prepare_workspace_branch",
        lambda settings, force_sync=False, branch_hint="": {
            "ok": True,
            "workspace": {
                "repo_path": "/tmp/ws/greenhillefka__pilotsuite-styx-core",
                "working_branch": branch_hint or "styx-self-repair-1",
                "head": "def5678",
                "actions": ["cloned", "fetched", "branch_prepared"],
            },
        },
    )

    app = _build_app()
    client = app.test_client()
    response = client.post("/api/v1/self-repair/workspace/prepare", json={"force_sync": True, "branch": "fix-1"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["workspace"]["working_branch"] == "fix-1"


def test_github_connection_test_and_save(monkeypatch):
    monkeypatch.setattr(
        self_repair,
        "_load_settings",
        lambda: {
            "enabled": True,
            "github": {
                "enabled": False,
                "token": "",
                "repo_owner": "",
                "repo_name": "",
                "repo_url": "",
            },
        },
    )

    def _fake_github_get(path: str, token: str, timeout: float = 8.0):
        if path == "/user":
            return 200, {"login": "pilotuser"}
        if path == "/repos/GreenhillEfka/pilotsuite-styx-core":
            return 200, {
                "default_branch": "main",
                "private": True,
                "permissions": {"pull": True, "push": True},
            }
        return 404, None

    monkeypatch.setattr(self_repair, "_github_get", _fake_github_get)

    saved = {}

    def _fake_update_settings(payload: dict):
        saved.update(payload)
        return {
            "enabled": True,
            "github": {
                "enabled": True,
                "token": "tok_test_1234",
                "repo_owner": "GreenhillEfka",
                "repo_name": "pilotsuite-styx-core",
                "repo_url": "https://github.com/GreenhillEfka/pilotsuite-styx-core.git",
            },
        }

    monkeypatch.setattr(self_repair, "_update_settings", _fake_update_settings)

    app = _build_app()
    client = app.test_client()
    response = client.post(
        "/api/v1/self-repair/github/test",
        json={
            "token": "tok_test_1234",
            "repo": "GreenhillEfka/pilotsuite-styx-core",
            "save": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["authenticated_as"] == "pilotuser"
    assert payload["repo"] == "GreenhillEfka/pilotsuite-styx-core"
    assert "github" in saved
