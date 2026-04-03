"""Health Analytics API Contract Tests."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import uuid

from copilot_core.analytics.health_analytics import HealthAnalyticsStore, HealthCheckEntryV1


@pytest.fixture
def temp_db():
    """Temporäres SQLite-DB für Tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "health_analytics.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """HealthAnalyticsStore Fixture."""
    return HealthAnalyticsStore(db_path=temp_db)


@pytest.fixture
def app(store):
    """Flask App mit Health Analytics Blueprint."""
    from flask import Flask
    from copilot_core.api.v1.health_analytics import create_blueprint, set_health_analytics_store

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Store setzen
    set_health_analytics_store(store)

    bp = create_blueprint()
    app.register_blueprint(bp)

    return app


@pytest.fixture
def client(app):
    """Test Client."""
    return app.test_client()


class TestHealthAnalyticsListChecks:
    """Tests für GET /api/v1/health/analytics/checks."""

    def test_list_checks_empty(self, client):
        """Leere Checks-Liste."""
        response = client.get("/api/v1/health/analytics/checks")
        assert response.status_code == 200
        data = response.get_json()
        assert data["entries"] == []
        assert data["total_count"] == 0
        assert data["revision"] == 0

    def test_list_checks_with_entries(self, client, store):
        """Checks-Liste mit Einträgen."""
        base_time = datetime.now(timezone.utc)

        for i in range(5):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0 + i,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/checks")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_count"] == 5
        assert len(data["entries"]) == 5

    def test_list_checks_filter_by_component(self, client, store):
        """Checks nach Komponente filtern."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        store.add_check_entry(entry1)

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        store.add_check_entry(entry2)

        response = client.get("/api/v1/health/analytics/checks?component=ha_connection")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_count"] == 1
        assert data["entries"][0]["component"] == "ha_connection"

    def test_list_checks_filter_by_status(self, client, store):
        """Checks nach Status filtern."""
        base_time = datetime.now(timezone.utc)

        for status in ["healthy", "degraded", "unhealthy"]:
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status=status,
                check_time=base_time.isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/checks?status=degraded")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_count"] == 1
        assert data["entries"][0]["status"] == "degraded"

    def test_list_checks_pagination(self, client, store):
        """Checks mit Pagination."""
        base_time = datetime.now(timezone.utc)

        for i in range(20):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/checks?limit=10&offset=0")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_count"] == 20
        assert len(data["entries"]) == 10

        response = client.get("/api/v1/health/analytics/checks?limit=10&offset=10")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["entries"]) == 10

    def test_list_checks_since_revision(self, client, store):
        """Checks mit since_revision für Delta-Polling."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        rev1 = store.add_check_entry(entry1)

        response = client.get(f"/api/v1/health/analytics/checks?since_revision={rev1}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_changes"] is False
        assert data["delta_revision"] == 0

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        rev2 = store.add_check_entry(entry2)

        response = client.get(f"/api/v1/health/analytics/checks?since_revision={rev1}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_changes"] is True
        assert data["delta_revision"] > 0


class TestHealthAnalyticsPatterns:
    """Tests für GET /api/v1/health/analytics/patterns."""

    def test_list_patterns_empty(self, client):
        """Leere Patterns-Liste."""
        response = client.get("/api/v1/health/analytics/patterns")
        assert response.status_code == 200
        data = response.get_json()
        assert data["patterns"] == []
        assert data["total_components"] == 0

    def test_list_patterns_with_data(self, client, store):
        """Patterns mit Daten."""
        base_time = datetime.now(timezone.utc)

        for i in range(10):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="ha_connection",
                component_type="ha_connection",
                status="healthy" if i < 8 else "degraded",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0 + i,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/patterns")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_components"] >= 1
        assert data["healthy_components"] >= 0

        ha_pattern = next((p for p in data["patterns"] if p["component"] == "ha_connection"), None)
        assert ha_pattern is not None
        assert ha_pattern["total_checks"] == 10
        assert ha_pattern["healthy_count"] == 8
        assert ha_pattern["degraded_count"] == 2

    def test_list_patterns_time_range(self, client, store):
        """Patterns mit Zeit-Filter."""
        base_time = datetime.now(timezone.utc)

        # Einträge außerhalb des Time-Range
        old_time = base_time - timedelta(days=30)
        for i in range(5):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="old_component",
                component_type="core",
                status="healthy",
                check_time=(old_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        # Einträge innerhalb des Time-Range
        for i in range(5):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="new_component",
                component_type="core",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/patterns?time_range_days=7")
        assert response.status_code == 200
        data = response.get_json()
        # Nur new_component sollte im 7-Tage-Fenster sein
        new_pattern = next((p for p in data["patterns"] if p["component"] == "new_component"), None)
        assert new_pattern is not None


class TestHealthAnalyticsEffectiveness:
    """Tests für GET /api/v1/health/analytics/effectiveness."""

    def test_get_effectiveness_empty(self, client):
        """Effectiveness ohne Daten."""
        response = client.get("/api/v1/health/analytics/effectiveness")
        assert response.status_code == 200
        data = response.get_json()
        assert "overall_health_score" in data
        assert "components_by_health" in data

    def test_get_effectiveness_with_data(self, client, store):
        """Effectiveness mit Daten."""
        base_time = datetime.now(timezone.utc)

        for i in range(100):
            status = "healthy" if i < 90 else "unhealthy"
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component=f"component_{i % 5}",
                component_type="core",
                status=status,
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/effectiveness")
        assert response.status_code == 200
        data = response.get_json()
        assert 0.85 <= data["overall_health_score"] <= 0.95
        assert data["checks_last_24h"] >= 100
        assert data["checks_last_7d"] >= 100


class TestHealthAnalyticsSummary:
    """Tests für GET /api/v1/health/analytics/summary."""

    def test_get_summary(self, client, store):
        """Analytics Summary."""
        base_time = datetime.now(timezone.utc)

        for i in range(10):
            entry = HealthCheckEntryV1(
                check_id=str(uuid.uuid4()),
                component="test_component",
                component_type="core",
                status="healthy",
                check_time=(base_time - timedelta(minutes=i)).isoformat(),
                response_time_ms=40.0,
            )
            store.add_check_entry(entry)

        response = client.get("/api/v1/health/analytics/summary")
        assert response.status_code == 200
        data = response.get_json()
        assert "history_summary" in data
        assert "patterns_summary" in data
        assert "effectiveness_summary" in data
        assert "revision" in data
        assert "generated_at" in data

    def test_get_summary_since_revision(self, client, store):
        """Summary mit since_revision."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        rev1 = store.add_check_entry(entry1)

        response = client.get(f"/api/v1/health/analytics/summary?since_revision={rev1}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_changes"] is False

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        rev2 = store.add_check_entry(entry2)

        response = client.get(f"/api/v1/health/analytics/summary?since_revision={rev1}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_changes"] is True


class TestHealthAnalyticsDeltaPolling:
    """Tests für Delta-Polling mit since_revision."""

    def test_delta_polling_checks(self, client, store):
        """Delta-Polling für Checks."""
        base_time = datetime.now(timezone.utc)

        # Initialer Stand
        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        rev1 = store.add_check_entry(entry1)

        # Poll mit since_revision=rev1
        response = client.get(f"/api/v1/health/analytics/checks?since_revision={rev1}")
        data = response.get_json()
        assert data["has_changes"] is False

        # Neuer Eintrag
        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="degraded",
            check_time=base_time.isoformat(),
            response_time_ms=100.0,
        )
        rev2 = store.add_check_entry(entry2)

        # Poll erneut - sollte Änderungen zeigen
        response = client.get(f"/api/v1/health/analytics/checks?since_revision={rev1}")
        data = response.get_json()
        assert data["has_changes"] is True
        assert data["delta_revision"] > 0

    def test_delta_polling_patterns(self, client, store):
        """Delta-Polling für Patterns."""
        base_time = datetime.now(timezone.utc)

        entry1 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ha_connection",
            component_type="ha_connection",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=40.0,
        )
        rev1 = store.add_check_entry(entry1)

        response = client.get(f"/api/v1/health/analytics/patterns?since_revision={rev1}")
        data = response.get_json()
        assert data["has_changes"] is False

        entry2 = HealthCheckEntryV1(
            check_id=str(uuid.uuid4()),
            component="ollama",
            component_type="ollama",
            status="healthy",
            check_time=base_time.isoformat(),
            response_time_ms=50.0,
        )
        rev2 = store.add_check_entry(entry2)

        response = client.get(f"/api/v1/health/analytics/patterns?since_revision={rev1}")
        data = response.get_json()
        assert data["has_changes"] is True
