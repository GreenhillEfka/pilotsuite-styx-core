"""Tests for Zone Aggregates API — Sammelentitaeten + Zone Scene Management."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from copilot_core.api.v1.zone_aggregates import (
    zone_aggregates_bp,
    init_zone_aggregates_api,
    ZONE_PRESETS,
    _save_scene,
    _load_zone_scenes,
    _load_scene,
    _delete_scene,
    _increment_apply_count,
    _init_scene_db,
    _scene_db,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Create temp DB path and initialize."""
    import copilot_core.api.v1.zone_aggregates as mod
    db_path = str(tmp_path / "test_scenes.sqlite3")
    mod._scene_db = db_path
    _init_scene_db()
    yield db_path
    mod._scene_db = ""


@pytest.fixture
def mock_aggregator():
    agg = MagicMock()
    from copilot_core.homeassistant.device_class_aggregator import AggregateResult, AggregateEntity
    agg.aggregate_zone.return_value = [
        AggregateResult(
            category_id="beleuchtung",
            name_de="Beleuchtung",
            icon="mdi:lightbulb-group",
            entity_count=2,
            entities=[
                AggregateEntity(entity_id="light.a", friendly_name="Licht A", state="on"),
                AggregateEntity(entity_id="light.b", friendly_name="Licht B", state="off"),
            ],
            summary={"on_count": 1, "off_count": 1, "total": 2},
        ),
    ]
    agg.get_category_defs.return_value = [
        {"category_id": "beleuchtung", "name_de": "Beleuchtung", "icon": "mdi:lightbulb-group",
         "domains": ["light"], "device_classes": [], "unit": ""},
    ]
    return agg


@pytest.fixture
def client(mock_aggregator, tmp_db):
    app = Flask(__name__)
    app.config["TESTING"] = True

    init_zone_aggregates_api(aggregator=mock_aggregator)

    # Override _scene_db AFTER init (which defaults to /data/)
    import copilot_core.api.v1.zone_aggregates as mod
    mod._scene_db = tmp_db
    _init_scene_db()

    app.register_blueprint(zone_aggregates_bp)
    with app.test_client() as c:
        yield c


class TestScenePersistence:
    def test_save_and_load(self, tmp_db):
        scene = {
            "scene_id": "test_1",
            "zone_id": "wohnbereich",
            "zone_name": "Wohnbereich",
            "name": "Test Scene",
            "entity_states": {"light.a": {"state": "on", "brightness": 200}},
            "created_at": 1710000000.0,
        }
        assert _save_scene(scene) is True
        loaded = _load_scene("test_1")
        assert loaded is not None
        assert loaded["scene_id"] == "test_1"
        assert loaded["entity_states"]["light.a"]["state"] == "on"

    def test_load_zone_scenes(self, tmp_db):
        for i in range(3):
            _save_scene({
                "scene_id": f"test_{i}",
                "zone_id": "wohnbereich",
                "name": f"Scene {i}",
                "entity_states": {},
                "created_at": 1710000000.0 + i,
            })
        _save_scene({
            "scene_id": "other_zone",
            "zone_id": "kueche",
            "name": "Kueche Scene",
            "entity_states": {},
            "created_at": 1710000000.0,
        })
        scenes = _load_zone_scenes("wohnbereich")
        assert len(scenes) == 3
        assert all(s["zone_id"] == "wohnbereich" for s in scenes)

    def test_delete_scene(self, tmp_db):
        _save_scene({
            "scene_id": "to_delete",
            "zone_id": "test",
            "name": "Delete Me",
            "entity_states": {},
            "created_at": 1710000000.0,
        })
        assert _delete_scene("to_delete") is True
        assert _load_scene("to_delete") is None

    def test_increment_apply_count(self, tmp_db):
        _save_scene({
            "scene_id": "count_test",
            "zone_id": "test",
            "name": "Count Test",
            "entity_states": {},
            "created_at": 1710000000.0,
            "applied_count": 0,
        })
        _increment_apply_count("count_test")
        loaded = _load_scene("count_test")
        assert loaded["applied_count"] == 1
        assert loaded["last_applied"] is not None

    def test_load_nonexistent(self, tmp_db):
        assert _load_scene("nonexistent") is None

    def test_delete_nonexistent(self, tmp_db):
        assert _delete_scene("nonexistent") is True  # DELETE is idempotent


class TestZonePresets:
    def test_presets_defined(self):
        assert len(ZONE_PRESETS) >= 8
        ids = {p["preset_id"] for p in ZONE_PRESETS}
        assert "morgen" in ids
        assert "abend" in ids
        assert "nacht" in ids
        assert "party" in ids
        assert "film" in ids

    def test_presets_have_actions(self):
        for p in ZONE_PRESETS:
            assert "actions" in p
            assert isinstance(p["actions"], dict)

    def test_presets_have_icons(self):
        for p in ZONE_PRESETS:
            assert p["icon"].startswith("mdi:")


class TestZoneAggregatesAPI:
    def test_get_categories(self, client):
        resp = client.get("/api/v1/zone/aggregates/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["count"] >= 1

    @patch("copilot_core.api.v1.zone_aggregates._get_zone")
    def test_get_zone_aggregates(self, mock_get_zone, client, mock_aggregator):
        mock_get_zone.return_value = {
            "zone_id": "wohnbereich",
            "name_de": "Wohnbereich",
            "entity_ids": ["light.a", "light.b"],
            "entities": {},
        }
        resp = client.get("/api/v1/zone/aggregates/wohnbereich")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["aggregates"]) >= 1
        assert data["aggregates"][0]["category_id"] == "beleuchtung"

    @patch("copilot_core.api.v1.zone_aggregates._get_zone")
    def test_get_zone_not_found(self, mock_get_zone, client):
        mock_get_zone.return_value = None
        resp = client.get("/api/v1/zone/aggregates/nonexistent")
        assert resp.status_code == 404

    def test_get_presets(self, client):
        resp = client.get("/api/v1/zone/aggregates/wohnbereich/presets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["presets"]) >= 8

    def test_get_zone_scenes_empty(self, client, tmp_db):
        resp = client.get("/api/v1/zone/aggregates/wohnbereich/scenes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 0

    def test_get_zone_scenes_with_data(self, client, tmp_db):
        _save_scene({
            "scene_id": "test_scene",
            "zone_id": "wohnbereich",
            "name": "Test",
            "entity_states": {"light.a": {"state": "on"}},
            "created_at": 1710000000.0,
        })
        resp = client.get("/api/v1/zone/aggregates/wohnbereich/scenes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        # entity_states should be stripped in list view
        assert "entity_states" not in data["scenes"][0]

    @patch("copilot_core.api.v1.zone_aggregates._get_zone")
    @patch("copilot_core.api.v1.zone_aggregates._capture_zone_states")
    def test_capture_scene(self, mock_capture, mock_get_zone, client, tmp_db):
        mock_get_zone.return_value = {
            "zone_id": "wohnbereich",
            "name_de": "Wohnbereich",
            "entity_ids": ["light.a"],
            "entities": {},
        }
        mock_capture.return_value = {"light.a": {"state": "on", "brightness": 200}}

        resp = client.post(
            "/api/v1/zone/aggregates/wohnbereich/scene/capture",
            json={"name": "Test Scene", "create_ha_scene": False},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert data["scene"]["zone_id"] == "wohnbereich"

        # Verify persistence
        scenes = _load_zone_scenes("wohnbereich")
        assert len(scenes) == 1

    @patch("copilot_core.api.v1.zone_aggregates._get_zone")
    @patch("copilot_core.api.v1.zone_aggregates._capture_zone_states")
    def test_capture_scene_no_entities(self, mock_capture, mock_get_zone, client, tmp_db):
        mock_get_zone.return_value = {
            "zone_id": "wohnbereich",
            "name_de": "Wohnbereich",
            "entity_ids": [],
            "entities": {},
        }
        mock_capture.return_value = {}
        resp = client.post(
            "/api/v1/zone/aggregates/wohnbereich/scene/capture",
            json={"name": "Empty"},
        )
        assert resp.status_code == 400

    def test_apply_scene_not_found(self, client, tmp_db):
        resp = client.post(
            "/api/v1/zone/aggregates/wohnbereich/scene/apply",
            json={"scene_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_apply_scene_missing_id(self, client):
        resp = client.post(
            "/api/v1/zone/aggregates/wohnbereich/scene/apply",
            json={},
        )
        assert resp.status_code == 400

    def test_delete_scene_api(self, client, tmp_db):
        _save_scene({
            "scene_id": "del_test",
            "zone_id": "wohnbereich",
            "name": "Delete",
            "entity_states": {},
            "created_at": 1710000000.0,
        })
        resp = client.delete("/api/v1/zone/aggregates/wohnbereich/scene/del_test")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
