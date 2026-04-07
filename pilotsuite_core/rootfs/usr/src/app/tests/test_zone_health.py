"""Tests for Zone Health API."""

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from copilot_core.api.v1.zone_health import (
    zone_health_bp,
    init_zone_health_api,
    ZoneHealthChecker,
    ZoneHealthResult,
    EntityHealth,
)


@pytest.fixture
def checker():
    return ZoneHealthChecker()


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    init_zone_health_api()
    app.register_blueprint(zone_health_bp)
    with app.test_client() as c:
        yield c


class TestZoneHealthResult:
    def test_to_dict(self):
        result = ZoneHealthResult(
            zone_id="wohnbereich",
            zone_name="Wohnbereich",
            health_score=85,
            status="healthy",
            total_entities=10,
            available_entities=9,
            unavailable_entities=1,
        )
        d = result.to_dict()
        assert d["zone_id"] == "wohnbereich"
        assert d["health_score"] == 85
        assert d["status"] == "healthy"
        assert "entity_details" not in d  # Not in summary

    def test_to_detail_dict(self):
        result = ZoneHealthResult(
            zone_id="wohnbereich",
            zone_name="Wohnbereich",
            health_score=85,
            status="healthy",
            entity_details=[
                EntityHealth(
                    entity_id="light.test",
                    friendly_name="Test Light",
                    domain="light",
                    state="on",
                    available=True,
                ),
            ],
        )
        d = result.to_detail_dict()
        assert "entity_details" in d
        assert len(d["entity_details"]) == 1
        assert d["entity_details"][0]["entity_id"] == "light.test"


class TestZoneHealthChecker:
    def test_empty_zone(self, checker):
        zone = {"zone_id": "test", "name_de": "Test", "entity_ids": [], "entities": {}}
        result = checker.check_zone(zone)
        assert result.health_score == 0
        assert result.status == "unknown"
        assert "Keine Entitaeten" in result.issues[0]

    def test_compute_score_full_health(self, checker):
        result = ZoneHealthResult(
            zone_id="test", zone_name="Test",
            health_score=0, status="",
            total_entities=10,
            available_entities=10,
            unavailable_entities=0,
            stale_entities=0,
            event_coverage={"lights": True, "motion": True, "climate": True, "sensors": True},
        )
        score = checker._compute_score(result)
        assert score >= 80

    def test_compute_score_degraded(self, checker):
        result = ZoneHealthResult(
            zone_id="test", zone_name="Test",
            health_score=0, status="",
            total_entities=10,
            available_entities=5,
            unavailable_entities=5,
            stale_entities=2,
            event_coverage={"lights": True, "motion": False, "climate": False, "sensors": True},
            issues=["Missing motion", "Missing climate"],
        )
        score = checker._compute_score(result)
        assert score < 80

    def test_compute_score_zero_entities(self, checker):
        result = ZoneHealthResult(
            zone_id="test", zone_name="Test",
            health_score=0, status="",
            total_entities=0,
        )
        assert checker._compute_score(result) == 0

    def test_score_to_status(self, checker):
        assert checker._score_to_status(90) == "healthy"
        assert checker._score_to_status(60) == "degraded"
        assert checker._score_to_status(30) == "critical"
        assert checker._score_to_status(0) == "unknown"

    @patch("copilot_core.api.v1.zone_health.http_requests.get")
    def test_check_zone_with_entities(self, mock_get, checker):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = [
            {
                "entity_id": "light.wohnzimmer",
                "state": "on",
                "last_updated": "2026-03-14T10:00:00+00:00",
                "last_changed": "2026-03-14T09:00:00+00:00",
                "attributes": {"friendly_name": "Wohnzimmer Licht"},
            },
            {
                "entity_id": "sensor.temp",
                "state": "unavailable",
                "last_updated": "2026-03-14T10:00:00+00:00",
                "last_changed": "2026-03-14T09:00:00+00:00",
                "attributes": {"friendly_name": "Temperatur"},
            },
        ]
        mock_get.return_value = mock_resp
        checker._token = "test-token"

        zone = {
            "zone_id": "wohnbereich",
            "name_de": "Wohnbereich",
            "entity_ids": ["light.wohnzimmer", "sensor.temp"],
            "entities": {"lights": ["light.wohnzimmer"]},
        }
        result = checker.check_zone(zone)
        assert result.total_entities == 2
        assert result.available_entities == 1
        assert result.unavailable_entities == 1
        assert result.status in ("healthy", "degraded", "critical")

    def test_check_zone_no_token(self, checker):
        checker._token = ""
        zone = {
            "zone_id": "test",
            "name_de": "Test",
            "entity_ids": ["light.test"],
            "entities": {},
        }
        result = checker.check_zone(zone)
        # Without token, entities can't be fetched
        assert result.unavailable_entities >= 0


class TestEntityHealth:
    def test_creation(self):
        eh = EntityHealth(
            entity_id="light.test",
            friendly_name="Test Light",
            domain="light",
            state="on",
            available=True,
        )
        assert eh.entity_id == "light.test"
        assert eh.available is True
        assert eh.stale is False
        assert eh.issues == []


class TestZoneHealthAPI:
    def test_get_all_zones_health(self, client):
        with patch.object(ZoneHealthChecker, "check_all_zones", return_value=[
            ZoneHealthResult(
                zone_id="wohnbereich", zone_name="Wohnbereich",
                health_score=90, status="healthy",
            ),
        ]):
            resp = client.get("/api/v1/zone/health")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["summary"]["total_zones"] == 1
            assert data["summary"]["healthy"] == 1

    def test_get_zone_detail_not_found(self, client):
        with patch.object(ZoneHealthChecker, "_get_zones", return_value=[]):
            resp = client.get("/api/v1/zone/health/nonexistent")
            assert resp.status_code == 404

    def test_get_zone_detail_found(self, client):
        zone_data = {
            "zone_id": "wohnbereich",
            "name_de": "Wohnbereich",
            "entity_ids": [],
            "entities": {},
        }
        with patch.object(ZoneHealthChecker, "_get_zones", return_value=[zone_data]):
            with patch.object(ZoneHealthChecker, "check_zone", return_value=ZoneHealthResult(
                zone_id="wohnbereich", zone_name="Wohnbereich",
                health_score=85, status="healthy",
            )):
                resp = client.get("/api/v1/zone/health/wohnbereich")
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["ok"] is True
                assert data["zone"]["health_score"] == 85
