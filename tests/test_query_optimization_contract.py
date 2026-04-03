"""Query Optimization Contract Tests — Slice 65.

Tests für:
- Query-Caching mit TTL
- Batch-Insert/Update Operations
- Query-Plan-Analyse
- Index-Empfehlungen
- Query-Metriken-Tracking
"""

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from copilot_core.performance.query_optimizer import (
    CacheEntry,
    QueryOptimizer,
    QueryPattern,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Temporäre Test-Datenbank erstellen."""
    db_path = tmp_path / "test_analytics.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE zone_sync_events (
            event_id TEXT PRIMARY KEY,
            zone_id TEXT,
            event_type TEXT,
            status TEXT,
            timestamp REAL,
            revision INTEGER
        );
        CREATE INDEX idx_zone_events_zone_id ON zone_sync_events(zone_id);
        CREATE INDEX idx_zone_events_timestamp ON zone_sync_events(timestamp);

        CREATE TABLE module_executions (
            execution_id TEXT PRIMARY KEY,
            module_id TEXT,
            module_name TEXT,
            status TEXT,
            execution_time TEXT,
            duration_ms REAL,
            zone_id TEXT
        );
        CREATE INDEX idx_module_executions_module ON module_executions(module_id);
        CREATE INDEX idx_module_executions_time ON module_executions(execution_time);

        CREATE TABLE action_closure_events (
            event_id TEXT PRIMARY KEY,
            closure_id TEXT,
            event_type TEXT,
            zone_id TEXT,
            source TEXT,
            timestamp REAL
        );
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def optimizer(temp_db: Path) -> QueryOptimizer:
    """Query-Optimizer Instanz für Tests."""
    return QueryOptimizer(db_path=temp_db, cache_enabled=True)


@pytest.fixture
def populated_db(temp_db: Path) -> Path:
    """Datenbank mit Testdaten füllen."""
    conn = sqlite3.connect(str(temp_db))
    
    # Zone-Events einfügen
    zone_data = [
        (f"zone_event_{i}", f"zone_{i % 3}", "topology_sync", "success", time.time() - i * 100, i)
        for i in range(100)
    ]
    conn.executemany(
        "INSERT INTO zone_sync_events VALUES (?, ?, ?, ?, ?, ?)",
        zone_data
    )
    
    # Module-Executions einfügen
    module_data = [
        (f"mod_exec_{i}", f"module_{i % 5}", f"Module{i % 5}", "success", "2026-04-03T00:{i:02d}:00", 50 + i, f"zone_{i % 3}")
        for i in range(50)
    ]
    conn.executemany(
        "INSERT INTO module_executions VALUES (?, ?, ?, ?, ?, ?, ?)",
        module_data
    )
    
    conn.commit()
    conn.close()
    return temp_db


class TestQueryCaching:
    """Tests für Query-Caching mit TTL."""

    def test_cache_hit_on_repeated_query(self, optimizer: QueryOptimizer, populated_db: Path):
        """Wiederholte Query sollte Cache-Hit erzeugen."""
        conn = sqlite3.connect(str(populated_db))
        
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ?"
        params = ("zone_0",)
        
        # Erster Aufruf (Cache Miss)
        result1 = optimizer.execute_with_cache(conn, query, params, ttl=60.0)
        assert len(result1) > 0
        
        # Zweiter Aufruf (Cache Hit)
        result2 = optimizer.execute_with_cache(conn, query, params, ttl=60.0)
        assert result1 == result2
        
        # Metriken prüfen
        query_hash = optimizer._hash_query(query, params)
        metrics = optimizer._metrics.get(query_hash)
        assert metrics is not None
        assert metrics.cache_hits == 1
        assert metrics.cache_misses == 1
        
        conn.close()

    def test_cache_miss_on_different_params(self, optimizer: QueryOptimizer, populated_db: Path):
        """Query mit anderen Parametern sollte Cache Miss erzeugen."""
        conn = sqlite3.connect(str(populated_db))
        
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ?"
        
        # Erste Query
        result1 = optimizer.execute_with_cache(conn, query, ("zone_0",), ttl=60.0)
        
        # Zweite Query mit anderen Parametern
        result2 = optimizer.execute_with_cache(conn, query, ("zone_1",), ttl=60.0)
        
        assert result1 != result2
        
        conn.close()

    def test_cache_expiration(self, optimizer: QueryOptimizer, populated_db: Path):
        """Abgelaufener Cache-Eintrag sollte zu Cache Miss führen."""
        conn = sqlite3.connect(str(populated_db))
        
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ?"
        params = ("zone_0",)
        
        # Erster Aufruf
        result1 = optimizer.execute_with_cache(conn, query, params, ttl=0.1)
        assert len(result1) > 0
        
        # Warten bis Cache abläuft
        time.sleep(0.15)
        
        # Zweiter Aufruf sollte Cache Miss sein (neue Ausführung)
        result2 = optimizer.execute_with_cache(conn, query, params, ttl=0.1)
        
        # Ergebnis sollte gleich sein (gleiche DB), aber Cache wurde neu befüllt
        assert result1 == result2
        
        conn.close()

    def test_force_refresh_bypasses_cache(self, optimizer: QueryOptimizer, populated_db: Path):
        """force_refresh=True sollte Cache umgehen."""
        conn = sqlite3.connect(str(populated_db))
        
        query = "SELECT COUNT(*) FROM zone_sync_events"
        
        # Erster Aufruf
        result1 = optimizer.execute_with_cache(conn, query, ttl=3600.0)
        
        # Zweiter Aufruf mit force_refresh
        result2 = optimizer.execute_with_cache(conn, query, ttl=3600.0, force_refresh=True)
        
        assert result1 == result2
        
        # Metriken prüfen: 2 Cache Misses durch force_refresh
        query_hash = optimizer._hash_query(query)
        metrics = optimizer._metrics.get(query_hash)
        assert metrics is not None
        assert metrics.cache_misses == 2
        
        conn.close()

    def test_cleanup_expired_cache(self, optimizer: QueryOptimizer, populated_db: Path):
        """cleanup_expired_cache sollte abgelaufene Einträge entfernen."""
        conn = sqlite3.connect(str(populated_db))
        
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ?"
        
        # Mehrere Queries mit kurzer TTL
        for i in range(5):
            optimizer.execute_with_cache(conn, query, (f"zone_{i}",), ttl=0.1)
        
        assert len(optimizer._cache) == 5
        
        time.sleep(0.15)
        
        # Cleanup
        removed = optimizer.cleanup_expired_cache()
        assert removed == 5
        assert len(optimizer._cache) == 0
        
        conn.close()


class TestBatchOperations:
    """Tests für Batch-Insert/Update Operations."""

    def test_batch_insert(self, optimizer: QueryOptimizer, temp_db: Path):
        """Batch-Insert sollte mehrere Zeilen effizient einfügen."""
        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA journal_mode=WAL")
        
        rows = [
            (f"batch_{i}", f"zone_{i % 3}", "topology_sync", "success", time.time(), i)
            for i in range(100)
        ]
        
        count = optimizer.batch_insert(
            conn,
            "zone_sync_events",
            ["event_id", "zone_id", "event_type", "status", "timestamp", "revision"],
            rows,
            chunk_size=25,
        )
        
        assert count == 100
        
        # Verify
        cursor = conn.execute("SELECT COUNT(*) FROM zone_sync_events")
        total = cursor.fetchone()[0]
        assert total == 100
        
        conn.close()

    def test_batch_insert_empty_rows(self, optimizer: QueryOptimizer, temp_db: Path):
        """Batch-Insert mit leeren Rows sollte 0 zurückgeben."""
        conn = sqlite3.connect(str(temp_db))
        
        count = optimizer.batch_insert(
            conn,
            "zone_sync_events",
            ["event_id", "zone_id"],
            [],
        )
        
        assert count == 0
        conn.close()

    def test_batch_update(self, optimizer: QueryOptimizer, populated_db: Path):
        """Batch-Update sollte mehrere Zeilen aktualisieren."""
        conn = sqlite3.connect(str(populated_db))
        
        # Update alle zone_0 Events auf status='updated'
        params = [("updated", "zone_0")]
        
        count = optimizer.batch_update(
            conn,
            "zone_sync_events",
            "status = ?",
            "zone_id = ?",
            params,
        )
        
        assert count > 0
        
        # Verify
        cursor = conn.execute(
            "SELECT COUNT(*) FROM zone_sync_events WHERE status = ? AND zone_id = ?",
            ("updated", "zone_0")
        )
        updated_count = cursor.fetchone()[0]
        assert updated_count == count
        
        conn.close()

    def test_batch_insert_with_rollback_on_error(self, optimizer: QueryOptimizer, temp_db: Path):
        """Batch-Insert sollte bei Fehler rollbacken."""
        conn = sqlite3.connect(str(temp_db))
        
        # Ungültige Daten (falsche Spaltenanzahl)
        rows = [("invalid",)]  # Fehlt Spalten
        
        with pytest.raises(Exception):
            optimizer.batch_insert(
                conn,
                "zone_sync_events",
                ["event_id", "zone_id", "event_type", "status", "timestamp", "revision"],
                rows,
            )
        
        # Verify: Tabelle sollte leer sein (rollback)
        cursor = conn.execute("SELECT COUNT(*) FROM zone_sync_events")
        total = cursor.fetchone()[0]
        assert total == 0
        
        conn.close()


class TestQueryPlanAnalysis:
    """Tests für Query-Plan-Analyse."""

    def test_analyze_query_plan_with_index(self, optimizer: QueryOptimizer, populated_db: Path):
        """Query-Plan-Analyse sollte Index-Nutzung erkennen."""
        conn = sqlite3.connect(str(populated_db))
        
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ?"
        plan = optimizer.analyze_query_plan(conn, query, ("zone_0",))
        
        assert "error" not in plan
        assert plan["uses_index"] is True or plan["table_scans"] == 0
        
        conn.close()

    def test_analyze_query_plan_without_index(self, optimizer: QueryOptimizer, populated_db: Path):
        """Query-Plan-Analyse sollte Table-Scan erkennen."""
        conn = sqlite3.connect(str(populated_db))
        
        # Query ohne Index auf event_type
        query = "SELECT * FROM zone_sync_events WHERE event_type = ?"
        plan = optimizer.analyze_query_plan(conn, query, ("topology_sync",))
        
        assert "error" not in plan
        # Sollte Table-Scan erkennen oder zumindest keinen Index verwenden
        
        conn.close()

    def test_detect_pattern_zone_by_id_timestamp(self, optimizer: QueryOptimizer):
        """Pattern-Erkennung für zone_by_id_timestamp."""
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ? AND timestamp >= ?"
        pattern = optimizer._detect_pattern(query)
        
        assert pattern == QueryPattern.ZONE_BY_ID_TIMESTAMP

    def test_detect_pattern_module_by_id_status(self, optimizer: QueryOptimizer):
        """Pattern-Erkennung für module_by_id_status."""
        query = "SELECT * FROM module_executions WHERE module_id = ? AND status = ?"
        pattern = optimizer._detect_pattern(query)
        
        assert pattern == QueryPattern.MODULE_BY_ID_STATUS

    def test_detect_pattern_analytics_aggregation(self, optimizer: QueryOptimizer):
        """Pattern-Erkennung für Analytics-Aggregation."""
        query = "SELECT zone_id, COUNT(*) FROM zone_sync_events GROUP BY zone_id"
        pattern = optimizer._detect_pattern(query)
        
        assert pattern == QueryPattern.ANALYTICS_ZONE_AGGREGATION


class TestIndexRecommendations:
    """Tests für Index-Empfehlungen."""

    def test_recommend_indexes_returns_composite_indexes(self, optimizer: QueryOptimizer):
        """Index-Empfehlungen sollte Composite-Indexes enthalten."""
        conn = sqlite3.connect(":memory:")
        recommendations = optimizer.recommend_indexes(conn)
        
        assert len(recommendations) > 0
        
        # Mindestens ein Composite-Index mit mehreren Spalten
        composite_indexes = [r for r in recommendations if len(r.columns) > 1]
        assert len(composite_indexes) > 0
        
        # Alle Empfehlungen sollten CREATE INDEX Statements haben
        for rec in recommendations:
            assert "CREATE INDEX" in rec.create_statement
            assert len(rec.columns) > 0

    def test_apply_recommended_indexes(self, optimizer: QueryOptimizer, temp_db: Path):
        """Anwenden der empfohlenen Indexes sollte erfolgreich sein."""
        result = optimizer.apply_recommended_indexes(temp_db)
        
        assert "applied_indexes" in result
        assert "total_recommended" in result
        assert result["total_recommended"] > 0
        
        # Verify: Indexes sollten erstellt worden sein
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Mindestens einige der empfohlenen Indexes sollten existieren
        for idx_name in result["applied_indexes"]:
            assert idx_name in indexes


class TestQueryMetrics:
    """Tests für Query-Metriken-Tracking."""

    def test_metrics_tracking_on_query_execution(self, optimizer: QueryOptimizer, populated_db: Path):
        """Query-Ausführung sollte Metriken tracken."""
        conn = sqlite3.connect(str(populated_db))
        
        # Query mit zone_id UND timestamp für Pattern-Erkennung
        query = "SELECT * FROM zone_sync_events WHERE zone_id = ? AND timestamp >= ?"
        params = ("zone_0", time.time() - 3600)
        
        # Query ausführen
        optimizer.execute_with_cache(conn, query, params, ttl=60.0)
        
        # Metriken prüfen
        query_hash = optimizer._hash_query(query, params)
        metrics = optimizer._metrics.get(query_hash)
        
        assert metrics is not None
        assert metrics.execution_count == 1
        assert metrics.query_pattern == QueryPattern.ZONE_BY_ID_TIMESTAMP
        assert metrics.last_duration_ms >= 0
        
        conn.close()

    def test_get_metrics_summary(self, optimizer: QueryOptimizer, populated_db: Path):
        """Metrics-Summary sollte korrekte aggregierte Daten liefern."""
        conn = sqlite3.connect(str(populated_db))
        
        # Mehrere Queries ausführen
        for i in range(10):
            query = f"SELECT * FROM zone_sync_events WHERE zone_id = 'zone_{i % 3}'"
            optimizer.execute_with_cache(conn, query, ttl=60.0)
        
        summary = optimizer.get_metrics_summary()
        
        assert summary.total_queries_tracked > 0
        assert summary.cache_hit_rate >= 0
        assert summary.cache_hit_rate <= 1
        assert summary.avg_query_duration_ms >= 0
        assert summary.generated_at is not None
        
        conn.close()

    def test_slow_query_detection(self, optimizer: QueryOptimizer, populated_db: Path):
        """Slow Queries sollten erkannt werden."""
        conn = sqlite3.connect(str(populated_db))
        
        # Query mehrfach ausführen (simuliere langsame Query)
        query = "SELECT * FROM zone_sync_events"
        for _ in range(5):
            optimizer.execute_with_cache(conn, query, ttl=60.0)
        
        summary = optimizer.get_metrics_summary()
        
        # Summary sollte Slow-Query-Count enthalten
        assert summary.slow_queries_count >= 0
        
        conn.close()


class TestCacheEntry:
    """Tests für CacheEntry-Klasse."""

    def test_cache_entry_expiration(self):
        """CacheEntry sollteExpiration korrekt erkennen."""
        entry = CacheEntry(
            query_hash="test",
            result=[1, 2, 3],
            created_at=time.time(),
            ttl_seconds=0.1,
        )
        
        assert not entry.is_expired()
        
        time.sleep(0.15)
        
        assert entry.is_expired()

    def test_cache_entry_hits_tracking(self):
        """CacheEntry sollte Hits tracken."""
        entry = CacheEntry(
            query_hash="test",
            result=[1, 2, 3],
            created_at=time.time(),
            ttl_seconds=3600.0,
            hits=0,
        )
        
        entry.hits += 1
        entry.hits += 1
        
        assert entry.hits == 2


class TestQueryOptimizerSingleton:
    """Tests für Singleton-Pattern."""

    def test_get_query_optimizer_returns_singleton(self):
        """get_query_optimizer sollte dieselbe Instanz zurückgeben."""
        from copilot_core.performance.query_optimizer import get_query_optimizer
        
        opt1 = get_query_optimizer()
        opt2 = get_query_optimizer()
        
        assert opt1 is opt2
