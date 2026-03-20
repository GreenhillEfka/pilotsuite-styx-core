"""Tests for proposal -> action intent policy gating."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest


@pytest.fixture
def client():
    from flask import Flask
    from copilot_core.api.v1.habitus import bp as habitus_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["COPILOT_CFG"] = Mock(data_dir="/tmp/test_data")
    app.register_blueprint(habitus_bp)

    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    return {"X-Auth-Token": "test-token-123"}


def _accept(client, auth_headers, payload: dict):
    return client.post(
        "/habitus/zone-proposals/accept",
        headers=auth_headers,
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_accept_learning_mode_stays_pending_styx_instruction(client, auth_headers):
    response = _accept(
        client,
        auth_headers,
        {
            "proposal": {
                "proposal_id": "proposal:light-1",
                "zone_id": "zone:wohnzimmer",
                "action": {
                    "domain": "light",
                    "entity_id": "light.wohnzimmer_main",
                    "suggested_service": "turn_on",
                    "state": "on",
                },
            },
            "module_overrides": {
                "light": {
                    "enabled": True,
                    "autonomy_mode": "learning",
                    "direct_execution_enabled": False,
                    "approval_required": True,
                    "output_adapter": "homeassistant",
                }
            },
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["proposal_intent"]["module_id"] == "light"
    assert data["action_intent"]["execution_state"] == "awaiting_styx_instruction"
    assert data["action_intent"]["eligible_for_execution"] is False
    assert "learning_mode_requires_styx_instruction" in data["action_intent"]["blocked_reasons"]
    assert data["habitat_module_command"]["command_mode"] == "preview_only"


def test_accept_autonomous_mode_can_become_ready_without_extra_instruction(client, auth_headers):
    response = _accept(
        client,
        auth_headers,
        {
            "proposal": {
                "proposal_id": "proposal:music-1",
                "zone_id": "zone:kueche",
                "action": {
                    "domain": "media_player",
                    "entity_id": "media_player.kueche_sonos",
                    "suggested_service": "media_play",
                    "state": "playing",
                },
            },
            "module_overrides": {
                "music": {
                    "enabled": True,
                    "autonomy_mode": "autonomous",
                    "direct_execution_enabled": True,
                    "approval_required": False,
                    "output_adapter": "homeassistant",
                }
            },
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["proposal_intent"]["module_id"] == "music"
    assert data["action_intent"]["execution_state"] == "ready_for_execution"
    assert data["action_intent"]["eligible_for_execution"] is True
    assert data["policy_gate"]["decision_source"] == "policy_autonomous"
    assert data["habitat_module_command"]["command_mode"] == "service_call_ready"


def test_accept_off_mode_remains_blocked_even_with_styx_instruction(client, auth_headers):
    response = _accept(
        client,
        auth_headers,
        {
            "proposal": {
                "proposal_id": "proposal:tv-1",
                "zone_id": "zone:schlafzimmer",
                "action": {
                    "domain": "media_player",
                    "entity_id": "media_player.bedroom_tv",
                    "suggested_service": "turn_on",
                    "state": "on",
                    "summary": "Turn TV on",
                },
            },
            "styx_instruction": True,
            "module_overrides": {
                "tv": {
                    "enabled": True,
                    "autonomy_mode": "off",
                    "direct_execution_enabled": True,
                    "approval_required": False,
                }
            },
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["proposal_intent"]["module_id"] == "tv"
    assert data["action_intent"]["execution_state"] == "blocked"
    assert data["action_intent"]["eligible_for_execution"] is False
    assert "autonomy_off" in data["action_intent"]["blocked_reasons"]


def test_unmapped_cover_action_stays_blocked_as_policy_gap(client, auth_headers):
    response = _accept(
        client,
        auth_headers,
        {
            "proposal": {
                "proposal_id": "proposal:cover-1",
                "zone_id": "zone:wohnzimmer",
                "action": {
                    "domain": "cover",
                    "entity_id": "cover.wohnzimmer_blinds",
                    "suggested_service": "close_cover",
                    "state": "closed",
                },
            },
            "styx_instruction": True,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["proposal_intent"]["module_id"] is None
    assert data["action_intent"]["execution_state"] == "blocked"
    assert "module_unmapped" in data["action_intent"]["blocked_reasons"]
    assert "zone_policy_unresolved" in data["action_intent"]["blocked_reasons"]
