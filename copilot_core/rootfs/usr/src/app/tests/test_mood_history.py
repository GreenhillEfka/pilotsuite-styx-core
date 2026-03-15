"""Tests for MoodHistoryStore -- mood snapshot persistence."""

import os
import tempfile
import time
import unittest

from copilot_core.neurons.mood_history import (
    MoodHistoryStore,
    reset_mood_history_store,
)


class TestMoodHistoryStore(unittest.TestCase):
    """Test MoodHistoryStore CRUD and lifecycle."""

    def setUp(self):
        """Create a fresh temp database for each test."""
        reset_mood_history_store()
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        # min_interval_s=0 disables rate limiting for tests
        self.store = MoodHistoryStore(
            db_path=self._tmp.name,
            retention_days=7,
            min_interval_s=0,
        )

    def tearDown(self):
        """Remove temp database."""
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass
        # Also remove WAL/SHM files
        for suffix in ("-wal", "-shm"):
            try:
                os.unlink(self._tmp.name + suffix)
            except OSError:
                pass
        reset_mood_history_store()

    # ------------------------------------------------------------------
    # record_snapshot
    # ------------------------------------------------------------------

    def test_record_snapshot_basic(self):
        """Test basic snapshot recording."""
        result = self.store.record_snapshot(
            mood="relax",
            confidence=0.85,
            mood_values={"relax": 0.85, "focus": 0.3, "sleep": 0.1},
        )
        self.assertTrue(result)

    def test_record_snapshot_with_zone_context(self):
        """Test recording with zone context."""
        result = self.store.record_snapshot(
            mood="focus",
            confidence=0.72,
            mood_values={"focus": 0.72, "relax": 0.2},
            zone_context={"zone": "office", "persons": ["person.andreas"]},
        )
        self.assertTrue(result)

    def test_record_snapshot_rate_limit(self):
        """Test that rate limiting prevents rapid recording."""
        store = MoodHistoryStore(
            db_path=self._tmp.name,
            min_interval_s=60,  # 60s rate limit
        )
        # First call should succeed
        self.assertTrue(store.record_snapshot("relax", 0.5, {"relax": 0.5}))
        # Second call within rate limit should be skipped
        self.assertFalse(store.record_snapshot("focus", 0.6, {"focus": 0.6}))

    def test_record_multiple_snapshots(self):
        """Test recording multiple snapshots."""
        moods = [
            ("relax", 0.8, {"relax": 0.8, "focus": 0.2}),
            ("focus", 0.7, {"relax": 0.3, "focus": 0.7}),
            ("sleep", 0.9, {"sleep": 0.9, "relax": 0.1}),
        ]
        for mood, conf, vals in moods:
            self.assertTrue(self.store.record_snapshot(mood, conf, vals))

        recent = self.store.get_recent(hours=1)
        self.assertEqual(len(recent), 3)

    # ------------------------------------------------------------------
    # get_recent
    # ------------------------------------------------------------------

    def test_get_recent_empty(self):
        """Test get_recent on empty store."""
        recent = self.store.get_recent(hours=24)
        self.assertEqual(recent, [])

    def test_get_recent_returns_ordered(self):
        """Test that recent snapshots are ordered by timestamp ascending."""
        self.store.record_snapshot("relax", 0.5, {"relax": 0.5})
        self.store.record_snapshot("focus", 0.6, {"focus": 0.6})
        self.store.record_snapshot("sleep", 0.7, {"sleep": 0.7})

        recent = self.store.get_recent(hours=1)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["mood"], "relax")
        self.assertEqual(recent[1]["mood"], "focus")
        self.assertEqual(recent[2]["mood"], "sleep")

    def test_get_recent_snapshot_structure(self):
        """Test the structure of a returned snapshot dict."""
        self.store.record_snapshot(
            "relax", 0.85,
            {"relax": 0.85, "focus": 0.3},
            zone_context={"zone": "living_room"},
        )
        recent = self.store.get_recent(hours=1)
        self.assertEqual(len(recent), 1)

        snap = recent[0]
        self.assertIn("id", snap)
        self.assertIn("ts", snap)
        self.assertEqual(snap["mood"], "relax")
        self.assertAlmostEqual(snap["confidence"], 0.85, places=2)
        self.assertIsInstance(snap["mood_values"], dict)
        self.assertEqual(snap["mood_values"]["relax"], 0.85)
        self.assertEqual(snap["zone_context"]["zone"], "living_room")

    def test_get_recent_no_zone_context(self):
        """Test snapshot without zone_context returns None for that field."""
        self.store.record_snapshot("focus", 0.6, {"focus": 0.6})
        snap = self.store.get_recent(hours=1)[0]
        self.assertIsNone(snap["zone_context"])

    # ------------------------------------------------------------------
    # get_trend
    # ------------------------------------------------------------------

    def test_get_trend_empty(self):
        """Test trend on empty store."""
        trend = self.store.get_trend(hours=24)
        self.assertEqual(trend["count"], 0)
        self.assertEqual(trend["distribution"], {})
        self.assertEqual(trend["dominant_mood"], "unknown")
        self.assertEqual(trend["period_hours"], 24)

    def test_get_trend_distribution(self):
        """Test trend distribution calculation."""
        for _ in range(3):
            self.store.record_snapshot("relax", 0.8, {"relax": 0.8})
        for _ in range(2):
            self.store.record_snapshot("focus", 0.7, {"focus": 0.7})
        self.store.record_snapshot("sleep", 0.9, {"sleep": 0.9})

        trend = self.store.get_trend(hours=1)
        self.assertEqual(trend["count"], 6)
        self.assertEqual(trend["distribution"]["relax"], 3)
        self.assertEqual(trend["distribution"]["focus"], 2)
        self.assertEqual(trend["distribution"]["sleep"], 1)
        self.assertEqual(trend["dominant_mood"], "relax")

    def test_get_trend_avg_confidence(self):
        """Test average confidence calculation."""
        self.store.record_snapshot("relax", 0.8, {"relax": 0.8})
        self.store.record_snapshot("relax", 0.6, {"relax": 0.6})

        trend = self.store.get_trend(hours=1)
        self.assertAlmostEqual(trend["avg_confidence"], 0.7, places=1)

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def test_cleanup_removes_old_snapshots(self):
        """Test that cleanup removes snapshots beyond retention."""
        # Insert a snapshot manually with old timestamp
        import sqlite3
        from datetime import datetime, timedelta, timezone

        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        with sqlite3.connect(self._tmp.name) as conn:
            conn.execute(
                """INSERT INTO mood_snapshots (ts, mood, confidence, mood_values)
                   VALUES (?, ?, ?, ?)""",
                (old_ts, "relax", 0.5, '{"relax": 0.5}'),
            )

        # Insert a recent one via the store
        self.store.record_snapshot("focus", 0.7, {"focus": 0.7})

        # Before cleanup: 2 snapshots
        all_snaps = self.store.get_recent(hours=24 * 365)
        # The old one is beyond default 168h lookback, count via SQL
        with sqlite3.connect(self._tmp.name) as conn:
            count = conn.execute("SELECT COUNT(*) FROM mood_snapshots").fetchone()[0]
        self.assertEqual(count, 2)

        # Run cleanup (retention = 7 days, old snapshot is 10 days old)
        deleted = self.store.cleanup()
        self.assertEqual(deleted, 1)

        # After cleanup: 1 snapshot
        with sqlite3.connect(self._tmp.name) as conn:
            count = conn.execute("SELECT COUNT(*) FROM mood_snapshots").fetchone()[0]
        self.assertEqual(count, 1)

    def test_cleanup_keeps_recent(self):
        """Test that cleanup keeps recent snapshots."""
        self.store.record_snapshot("relax", 0.8, {"relax": 0.8})
        deleted = self.store.cleanup()
        self.assertEqual(deleted, 0)
        self.assertEqual(len(self.store.get_recent(hours=1)), 1)

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    def test_get_stats_empty(self):
        """Test stats on empty store."""
        stats = self.store.get_stats()
        self.assertEqual(stats["total_snapshots"], 0)
        self.assertIsNone(stats["oldest"])
        self.assertIsNone(stats["newest"])
        self.assertEqual(stats["retention_days"], 7)

    def test_get_stats_with_data(self):
        """Test stats after recording snapshots."""
        self.store.record_snapshot("relax", 0.8, {"relax": 0.8})
        self.store.record_snapshot("focus", 0.7, {"focus": 0.7})

        stats = self.store.get_stats()
        self.assertEqual(stats["total_snapshots"], 2)
        self.assertIsNotNone(stats["oldest"])
        self.assertIsNotNone(stats["newest"])

    # ------------------------------------------------------------------
    # Integration: record + retrieve
    # ------------------------------------------------------------------

    def test_roundtrip(self):
        """Test full record-then-retrieve cycle."""
        values = {"relax": 0.85, "focus": 0.3, "sleep": 0.1, "alert": 0.05}
        ctx = {"zone": "wohnzimmer", "persons": 2}

        self.store.record_snapshot("relax", 0.85, values, zone_context=ctx)

        recent = self.store.get_recent(hours=1)
        self.assertEqual(len(recent), 1)
        snap = recent[0]
        self.assertEqual(snap["mood"], "relax")
        self.assertAlmostEqual(snap["confidence"], 0.85, places=2)
        self.assertEqual(snap["mood_values"], values)
        self.assertEqual(snap["zone_context"], ctx)

        trend = self.store.get_trend(hours=1)
        self.assertEqual(trend["count"], 1)
        self.assertEqual(trend["dominant_mood"], "relax")


class TestMoodHistoryAPI(unittest.TestCase):
    """Test mood history API endpoints via Flask test client."""

    def setUp(self):
        """Set up Flask app with neurons blueprint."""
        reset_mood_history_store()
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()

        # Patch the store before importing endpoints
        import copilot_core.neurons.mood_history as mh_mod
        mh_mod._store_instance = MoodHistoryStore(
            db_path=self._tmp.name,
            min_interval_s=0,
        )

        from flask import Flask
        from copilot_core.api.v1.neurons import bp as neurons_bp

        self.app = Flask(__name__)
        self.app.register_blueprint(neurons_bp, url_prefix="/api/v1/neurons")
        self.client = self.app.test_client()
        self.store = mh_mod._store_instance

    def tearDown(self):
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass
        for suffix in ("-wal", "-shm"):
            try:
                os.unlink(self._tmp.name + suffix)
            except OSError:
                pass
        reset_mood_history_store()

    def test_mood_history_endpoint_empty(self):
        """Test /mood/history returns empty list when no data."""
        resp = self.client.get("/api/v1/neurons/mood/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["count"], 0)
        self.assertEqual(data["data"]["history"], [])

    def test_mood_history_endpoint_with_data(self):
        """Test /mood/history returns recorded snapshots."""
        self.store.record_snapshot("relax", 0.8, {"relax": 0.8})
        self.store.record_snapshot("focus", 0.7, {"focus": 0.7})

        resp = self.client.get("/api/v1/neurons/mood/history?hours=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["count"], 2)
        self.assertEqual(data["data"]["hours"], 1)

    def test_mood_history_invalid_hours(self):
        """Test /mood/history rejects invalid hours param."""
        resp = self.client.get("/api/v1/neurons/mood/history?hours=abc")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_mood_history_hours_capped(self):
        """Test hours is capped at 168 (7 days)."""
        resp = self.client.get("/api/v1/neurons/mood/history?hours=9999")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["data"]["hours"], 168)

    def test_mood_trend_endpoint_empty(self):
        """Test /mood/trend returns zero-state when empty."""
        resp = self.client.get("/api/v1/neurons/mood/trend")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["count"], 0)
        self.assertEqual(data["data"]["dominant_mood"], "unknown")

    def test_mood_trend_endpoint_with_data(self):
        """Test /mood/trend returns correct distribution."""
        for _ in range(3):
            self.store.record_snapshot("relax", 0.8, {"relax": 0.8})
        self.store.record_snapshot("focus", 0.6, {"focus": 0.6})

        resp = self.client.get("/api/v1/neurons/mood/trend?hours=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        trend = data["data"]
        self.assertEqual(trend["count"], 4)
        self.assertEqual(trend["distribution"]["relax"], 3)
        self.assertEqual(trend["distribution"]["focus"], 1)
        self.assertEqual(trend["dominant_mood"], "relax")

    def test_mood_trend_invalid_hours(self):
        """Test /mood/trend rejects invalid hours param."""
        resp = self.client.get("/api/v1/neurons/mood/trend?hours=xyz")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
