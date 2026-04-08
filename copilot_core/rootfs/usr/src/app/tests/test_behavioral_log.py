"""Tests for BehavioralLog — RAG-indexed autonomy history."""

import time
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.autonomy.behavioral_log import (
    ActionLogEntry,
    BehavioralLog,
    MAX_DOCUMENTS,
    NAMESPACE,
    RETENTION_DAYS,
    _format_log_text,
    _time_of_day,
)


class TestTimeOfDay:
    def test_morning(self):
        # 8:00 UTC
        ts = 1710403200.0  # 2024-03-14 08:00 UTC
        assert _time_of_day(ts) == "Morgen"

    def test_afternoon(self):
        ts = 1710424800.0  # 2024-03-14 14:00 UTC
        assert _time_of_day(ts) == "Nachmittag"

    def test_evening(self):
        ts = 1710439200.0  # 2024-03-14 18:00 UTC
        assert _time_of_day(ts) == "Abend"

    def test_night(self):
        ts = 1710453600.0  # 2024-03-14 22:00 UTC
        assert _time_of_day(ts) == "Nacht"


class TestFormatLogText:
    def test_light_action(self):
        entry = ActionLogEntry(
            zone_id="wohnbereich",
            module_id="licht",
            action="light.turn_on",
            mood="relax",
            confidence=0.82,
            weather="bewoelkt",
            details={"brightness_pct": 50, "color_temp_k": 2700},
        )
        text = _format_log_text(entry)
        assert "Wohnbereich" in text
        assert "50%" in text
        assert "2700K" in text
        assert "relax" in text
        assert "82%" in text
        assert "bewoelkt" in text

    def test_music_action(self):
        entry = ActionLogEntry(
            zone_id="wohnbereich",
            module_id="musik",
            action="music.play_favorite",
            mood="social",
            details={"music_favorite": "Party Mix"},
        )
        text = _format_log_text(entry)
        assert "Party Mix" in text
        assert "Wohnbereich" in text

    def test_generic_action(self):
        entry = ActionLogEntry(
            zone_id="kueche",
            module_id="klima",
            action="climate.set_temp",
            mood="active",
        )
        text = _format_log_text(entry)
        assert "climate.set_temp" in text
        assert "Kueche" in text


class TestBehavioralLogNoIndex:
    """BehavioralLog without BM25 index."""

    def test_log_action_no_index(self):
        log = BehavioralLog(bm25_index=None)
        log._init_done = True  # Skip lazy init
        entry = ActionLogEntry(
            zone_id="test", module_id="licht",
            action="light.turn_on", mood="relax",
        )
        assert log.log_action(entry) is False

    def test_query_history_no_index(self):
        log = BehavioralLog(bm25_index=None)
        log._init_done = True
        assert log.query_history("test") == []

    def test_get_stats_no_index(self):
        log = BehavioralLog(bm25_index=None)
        log._init_done = True
        stats = log.get_stats()
        assert stats["available"] is False


class TestBehavioralLogWithIndex:
    """BehavioralLog with real BM25 index."""

    @pytest.fixture
    def log_with_index(self, tmp_path):
        from copilot_core.rag.bm25 import BM25Config, BM25SqliteIndex
        config = BM25Config(db_path=str(tmp_path / "test_rag.sqlite3"))
        index = BM25SqliteIndex(config)
        return BehavioralLog(bm25_index=index)

    def test_log_and_query(self, log_with_index):
        entry = ActionLogEntry(
            zone_id="wohnbereich",
            module_id="licht",
            action="light.turn_on",
            mood="relax",
            confidence=0.85,
            weather="bewoelkt",
            details={"brightness_pct": 50, "color_temp_k": 2700},
        )
        assert log_with_index.log_action(entry) is True

        results = log_with_index.query_history("Wohnbereich Licht")
        assert len(results) >= 1
        assert "wohnbereich" in results[0]["text"].lower()

    def test_zone_history(self, log_with_index):
        for i in range(3):
            entry = ActionLogEntry(
                zone_id="schlafzimmer",
                module_id="licht",
                action="light.turn_on",
                mood="sleep",
                doc_id=f"test_{i}",
            )
            log_with_index.log_action(entry)

        results = log_with_index.get_zone_history("schlafzimmer")
        assert len(results) >= 1

    def test_get_stats(self, log_with_index):
        entry = ActionLogEntry(
            zone_id="test", module_id="licht",
            action="test", mood="test",
        )
        log_with_index.log_action(entry)
        stats = log_with_index.get_stats()
        assert stats["available"] is True
        assert stats["doc_count"] >= 1


class TestPrune:
    """Tests for _prune() retention and cap logic."""

    def test_prune_deletes_old_documents(self, tmp_path):
        """Verify _prune removes documents older than RETENTION_DAYS."""
        from copilot_core.rag.bm25 import BM25Config, BM25Document, BM25SqliteIndex

        config = BM25Config(db_path=str(tmp_path / "prune_test.sqlite3"))
        index = BM25SqliteIndex(config)
        log = BehavioralLog(bm25_index=index)

        # Insert a document with old timestamp via direct SQL
        old_ts = time.time() - (RETENTION_DAYS + 1) * 86400  # Older than retention
        doc = BM25Document(doc_id="old_doc", text="alte Aktion Wohnbereich", metadata={})
        index.upsert_documents(namespace=NAMESPACE, documents=[doc])

        # Backdate the created_at to be older than retention
        conn = index._get_conn()
        conn.execute(
            "UPDATE bm25_docs SET created_at = ? WHERE doc_id = ? AND namespace = ?",
            (old_ts, "old_doc", NAMESPACE),
        )
        conn.commit()

        # Insert a recent document
        recent_doc = BM25Document(doc_id="new_doc", text="neue Aktion", metadata={})
        index.upsert_documents(namespace=NAMESPACE, documents=[recent_doc])

        # Verify both exist
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM bm25_docs WHERE namespace = ?",
            (NAMESPACE,),
        ).fetchone()
        assert row["cnt"] == 2

        # Run prune
        log._prune()

        # Old doc should be gone, new doc should remain
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM bm25_docs WHERE namespace = ?",
            (NAMESPACE,),
        ).fetchone()
        assert row["cnt"] == 1

        remaining = conn.execute(
            "SELECT doc_id FROM bm25_docs WHERE namespace = ?",
            (NAMESPACE,),
        ).fetchone()
        assert remaining["doc_id"] == "new_doc"

    def test_prune_called_on_log_action(self, tmp_path):
        """Verify _prune is called after each log_action."""
        from copilot_core.rag.bm25 import BM25Config, BM25SqliteIndex

        config = BM25Config(db_path=str(tmp_path / "prune_call.sqlite3"))
        index = BM25SqliteIndex(config)
        log = BehavioralLog(bm25_index=index)

        with patch.object(log, "_prune", wraps=log._prune) as mock_prune:
            entry = ActionLogEntry(
                zone_id="test", module_id="licht",
                action="light.turn_on", mood="relax",
            )
            assert log.log_action(entry) is True
            mock_prune.assert_called_once()

    def test_prune_no_index(self):
        """_prune with no index does nothing (no crash)."""
        log = BehavioralLog(bm25_index=None)
        log._init_done = True
        # Should not raise
        log._prune()
