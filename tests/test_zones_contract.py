from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_zones_contract_exposes_minimal_read_only_catalog():
    client = create_app({"TESTING": True}).test_client()

    response = client.get("/api/v1/zones")
    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "ok"
    assert data["source"] == "static_habitus_catalog"
    assert data["total_zones"] == 10

    first = data["zones"][0]
    assert sorted(first) == [
        "description",
        "id",
        "keywords_de",
        "keywords_en",
        "name_de",
        "name_en",
        "priority",
        "zone_type",
    ]


def test_zones_contract_supports_exact_filter_and_rejects_unknown_zone_type(client):
    filtered = client.get("/api/v1/zones?zone_type=living")
    assert filtered.status_code == 200
    assert filtered.get_json()["total_zones"] == 1
    assert filtered.get_json()["zones"][0]["zone_type"] == "living"

    invalid = client.get("/api/v1/zones?zone_type=invalid")
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_zone_type"
    assert "living" in invalid.get_json()["valid_zone_types"]
