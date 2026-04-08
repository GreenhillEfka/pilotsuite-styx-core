from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ENDPOINTS: list[str] = []
PUBLIC_RUNTIME_ENDPOINTS = [
    "/health",
    "/version",
    "/api/v1/presence",
    "/api/v1/analytics",
    "/api/v1/notifications",
    "/api/v1/notifications/digest",
    "/api/v1/notifications/pending",
    "/api/v1/notifications/stats",
    "/api/v1/zones",
    "/api/v1/widgets/positions",
    "/api/v1/widgets/positions/bulk",
    "/api/v1/widgets/positions/{widget_id}",
    "/api/v1/widgets/positions/{widget_id}/history",
    "/api/v1/widgets/positions/{widget_id}/undo",
    "/api/v1/widgets/positions/{widget_id}/redo",
    "/api/v1/widgets/positions/reset",
]


def test_readme_api_table_matches_current_public_runtime_and_marks_remaining_legacy_paths_removed():
    readme = (REPO_ROOT / "README.md").read_text()
    endpoint_section = readme.split("## API Endpoints", 1)[1].split("## ", 1)[0]
    table_text = "\n".join(line for line in endpoint_section.splitlines() if line.strip().startswith("|"))
    note_text = endpoint_section.replace(table_text, "")

    for endpoint in PUBLIC_RUNTIME_ENDPOINTS:
        assert endpoint in table_text

    assert "Nicht Teil der aktuellen `v20`-Runtime" in note_text
    assert "/version" not in note_text
    assert "/api/v1/presence" not in note_text
    assert "/api/v1/analytics" not in note_text
    assert "/api/v1/notifications/digest" not in note_text
    assert "/api/v1/notifications/pending" not in note_text
    assert "/api/v1/notifications/stats" not in note_text
    assert "/api/v1/zones" not in note_text
    for endpoint in LEGACY_ENDPOINTS:
        assert endpoint not in table_text
        assert endpoint in note_text


def test_readme_no_longer_overclaims_unrebased_feature_domains():
    readme = (REPO_ROOT / "README.md").read_text()

    for stale_feature in ["Presence Detection", "Analytics Engine", "Notification System"]:
        assert stale_feature not in readme


def test_openapi_public_surface_matches_current_runtime_and_excludes_legacy_paths():
    spec = json.loads((REPO_ROOT / "docs" / "openapi.json").read_text())

    assert sorted(spec["paths"]) == sorted(PUBLIC_RUNTIME_ENDPOINTS)
    assert "Legacy-Endpunkte" in spec["info"]["description"]
    assert "`/version`" in spec["info"]["description"]
    assert "`/api/v1/presence`" in spec["info"]["description"]
    assert "`/api/v1/analytics`" in spec["info"]["description"]
    assert "`/api/v1/notifications`" in spec["info"]["description"]
    assert "`/api/v1/notifications/digest`" in spec["info"]["description"]
    assert "`/api/v1/notifications/pending`" in spec["info"]["description"]
    assert "`/api/v1/notifications/stats`" in spec["info"]["description"]
    assert "`/api/v1/zones`" in spec["info"]["description"]

    for endpoint in LEGACY_ENDPOINTS:
        assert endpoint not in spec["paths"]
