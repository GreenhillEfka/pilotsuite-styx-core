from __future__ import annotations

import json
from flask import Flask
from unittest.mock import patch

from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
from copilot_core.api.v1.suggestions import init_suggestions_api, suggestions_bp
from copilot_core.api.v1.proposals import init_proposals_api, proposals_bp


def _build_client():
    engine = AutomationSuggestionEngine()
    suggestion = engine.suggest_from_presence(away_minutes=45)

    app = Flask(__name__)
    init_suggestions_api(engine)
    init_proposals_api(engine)
    app.register_blueprint(suggestions_bp)
    app.register_blueprint(proposals_bp)
    return app, engine, suggestion.id


def test_accept_creates_proposal_and_lists():
    app, _engine, suggestion_id = _build_client()
    with patch("copilot_core.api.security.validate_token", lambda _request: True):
        client = app.test_client()
        accept_resp = client.post("/api/v1/suggestions/accept", json={"id": suggestion_id})
        assert accept_resp.status_code == 200
        data = json.loads(accept_resp.data)
        assert data["ok"] is True
        assert "proposal_id" in data
        proposal_id = data["proposal_id"]

        proposals_resp = client.get("/api/v1/proposals")
        assert proposals_resp.status_code == 200
        proposals_data = json.loads(proposals_resp.data)
        assert proposals_data["ok"] is True
        assert proposals_data["count"] == 1
        assert proposals_data["proposals"][0]["proposal_id"] == proposal_id

        suggestion_list = client.get("/api/v1/suggestions")
        assert suggestion_list.status_code == 200
        suggestions_data = json.loads(suggestion_list.data)
        assert suggestions_data["ok"] is True
        assert all(item["id"] != suggestion_id for item in suggestions_data["suggestions"])


def test_proposal_execute_emits_action_intent():
    app, _engine, suggestion_id = _build_client()
    with patch("copilot_core.api.security.validate_token", lambda _request: True):
        client = app.test_client()
        accept_resp = client.post("/api/v1/suggestions/accept", json={"id": suggestion_id})
        assert accept_resp.status_code == 200
        proposal_id = json.loads(accept_resp.data)["proposal_id"]

        detail_resp = client.get(f"/api/v1/proposals/{proposal_id}")
        assert detail_resp.status_code == 200
        detail = json.loads(detail_resp.data)
        assert detail["proposal"]["proposal_id"] == proposal_id

        execute_resp = client.post(f"/api/v1/proposals/{proposal_id}/execute", json={"dry_run": True})
        assert execute_resp.status_code == 200
        exec_payload = json.loads(execute_resp.data)
        assert exec_payload["ok"] is True
        assert exec_payload["dry_run"] is True
        intent = exec_payload["intent"]
        assert intent["proposal_id"] == proposal_id
        assert intent["status"] in {"ready", "executed", "pending"}


def test_execute_unknown_proposal_returns_404():
    app, _engine, _sid = _build_client()
    with patch("copilot_core.api.security.validate_token", lambda _request: True):
        client = app.test_client()
        resp = client.post("/api/v1/proposals/missing-proposal-id/execute", json={})
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["ok"] is False
