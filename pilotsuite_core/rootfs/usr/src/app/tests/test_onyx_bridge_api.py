"""Tests for Onyx bridge endpoints."""

from __future__ import annotations

import tempfile
from dataclasses import replace

from copilot_core.app import create_app


class _Resp:
    def __init__(self, status_code: int = 200, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


def _create_test_app(tmpdir: str):
    app = create_app()
    cfg = app.config["COPILOT_CFG"]
    app.config["COPILOT_CFG"] = replace(
        cfg,
        data_dir=tmpdir,
        brain_graph_json_path=f"{tmpdir}/brain_graph.db",
        events_jsonl_path=f"{tmpdir}/events.jsonl",
        candidates_json_path=f"{tmpdir}/candidates.json",
        brain_graph_nodes_max=500,
        brain_graph_edges_max=1500,
        brain_graph_persist=True,
    )
    return app


def test_onyx_status_reports_bridge(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_API", "http://supervisor/core/api")

    def _fake_get(url, headers=None, timeout=0):
        assert url.endswith("/config")
        assert headers["Authorization"] == "Bearer test-token"
        return _Resp(200, {"location_name": "Home"})

    monkeypatch.setattr("copilot_core.api.v1.onyx_bridge.http_requests.get", _fake_get)

    with tempfile.TemporaryDirectory() as tmpdir:
        app = _create_test_app(tmpdir)
        client = app.test_client()
        resp = client.get("/api/v1/onyx/status")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is True
        assert payload["bridge"] == "onyx"
        assert payload["ha_reachable"] is True


def test_onyx_service_call_success_with_readback(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_API", "http://supervisor/core/api")

    calls = {"post": None, "gets": []}

    def _fake_post(url, json=None, headers=None, timeout=0):
        calls["post"] = {"url": url, "json": json, "headers": headers}
        return _Resp(200, [{"entity_id": "light.retrolampe"}])

    def _fake_get(url, headers=None, timeout=0):
        calls["gets"].append(url)
        if url.endswith("/config"):
            return _Resp(200, {"location_name": "Home"})
        return _Resp(
            200,
            {
                "entity_id": "light.retrolampe",
                "state": "on",
                "attributes": {"friendly_name": "Retro Lampe"},
                "last_changed": "2026-02-22T20:00:00+00:00",
            },
        )

    monkeypatch.setattr("copilot_core.api.v1.onyx_bridge.http_requests.post", _fake_post)
    monkeypatch.setattr("copilot_core.api.v1.onyx_bridge.http_requests.get", _fake_get)

    with tempfile.TemporaryDirectory() as tmpdir:
        app = _create_test_app(tmpdir)
        client = app.test_client()
        resp = client.post(
            "/api/v1/onyx/ha/service-call",
            json={
                "domain": "light",
                "service": "turn_on",
                "entity_id": "light.retrolampe",
                "service_data": {"brightness_pct": 42},
            },
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["ok"] is True
        assert payload["domain"] == "light"
        assert payload["service"] == "turn_on"
        assert payload["entity_ids"] == ["light.retrolampe"]
        assert payload["readback_states"][0]["state"] == "on"
        assert calls["post"]["url"].endswith("/services/light/turn_on")
        assert calls["post"]["json"]["entity_id"] == "light.retrolampe"


def test_onyx_service_call_rejects_blocked_domain(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    monkeypatch.setenv("ONYX_ALLOWED_SERVICE_DOMAINS", "light,switch")

    with tempfile.TemporaryDirectory() as tmpdir:
        app = _create_test_app(tmpdir)
        client = app.test_client()
        resp = client.post(
            "/api/v1/onyx/ha/service-call",
            json={"domain": "climate", "service": "set_temperature"},
        )
        assert resp.status_code == 403
        payload = resp.get_json()
        assert payload["ok"] is False
        assert "not allowed" in payload["error"]


def test_onyx_service_call_requires_supervisor_token(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        app = _create_test_app(tmpdir)
        client = app.test_client()
        resp = client.post(
            "/api/v1/onyx/ha/service-call",
            json={"domain": "light", "service": "turn_on", "entity_id": "light.retrolampe"},
        )
        assert resp.status_code == 503
        payload = resp.get_json()
        assert payload["ok"] is False
        assert "SUPERVISOR_TOKEN" in payload["error"]
