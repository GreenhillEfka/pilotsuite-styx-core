"""Behavioral Log — RAG-indexed history of autonomous actions.

Every auto-execution is logged as a BM25 document in namespace "autonomy_log",
enabling chat queries like "Warum laeuft im Wohnzimmer Musik?" to find
relevant autonomy history.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

NAMESPACE = "autonomy_log"
MAX_DOCUMENTS = 5000
RETENTION_DAYS = 30


@dataclass
class ActionLogEntry:
    """A logged autonomous action."""

    zone_id: str
    module_id: str
    action: str  # e.g. "light.turn_on", "music.play_favorite"
    mood: str
    confidence: float = 0.0
    weather: str = ""
    trigger: str = ""  # "mood.changed" | "presence.changed"
    result: str = "ok"  # "ok" | "error" | "skipped"
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    doc_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


def _time_of_day(ts: float) -> str:
    """Classify timestamp into Tageszeit (Europe/Berlin)."""
    try:
        from zoneinfo import ZoneInfo
        berlin = ZoneInfo("Europe/Berlin")
    except ImportError:
        from datetime import timedelta
        berlin = timezone(timedelta(hours=1))
    hour = datetime.fromtimestamp(ts, tz=berlin).hour
    if 5 <= hour < 12:
        return "Morgen"
    if 12 <= hour < 17:
        return "Nachmittag"
    if 17 <= hour < 22:
        return "Abend"
    return "Nacht"


def _format_log_text(entry: ActionLogEntry) -> str:
    """Format log entry as human-readable German text for BM25 indexing."""
    zone_display = entry.zone_id.replace("_", " ").title()
    parts = [f"Autonome Aktion in {zone_display}:"]

    details = entry.details
    if "brightness_pct" in details:
        ct = details.get("color_temp_k", "")
        ct_str = f" ({ct}K Warmweiss)" if ct else ""
        parts.append(
            f"Licht auf {details['brightness_pct']}%{ct_str} eingestellt."
        )
    elif "music_favorite" in details:
        parts.append(f"Musik '{details['music_favorite']}' gestartet.")
    elif entry.action:
        parts.append(f"Aktion: {entry.action}.")

    if entry.mood:
        conf_str = f" ({int(entry.confidence * 100)}% Konfidenz)" if entry.confidence else ""
        parts.append(f"Grund: Stimmung '{entry.mood}' erkannt{conf_str}.")

    meta = []
    meta.append(f"Zone: {entry.zone_id}")
    meta.append(f"Modul: {entry.module_id}")
    if entry.weather:
        meta.append(f"Wetter: {entry.weather}")
    meta.append(f"Tageszeit: {_time_of_day(entry.timestamp)}")

    parts.append(" ".join(meta) + ".")
    return " ".join(parts)


class BehavioralLog:
    """Log autonomous actions to BM25 index for RAG retrieval."""

    def __init__(self, bm25_index=None) -> None:
        self._index = bm25_index
        self._init_done = False

    def _get_index(self):
        """Lazy-init BM25 index."""
        if self._index is not None:
            return self._index
        if self._init_done:
            return None
        self._init_done = True
        try:
            from copilot_core.rag.bm25 import BM25Config, BM25SqliteIndex
            self._index = BM25SqliteIndex(BM25Config())
            _LOGGER.info("BehavioralLog: BM25 index initialized")
        except Exception:
            _LOGGER.exception("BehavioralLog: Failed to init BM25 index")
        return self._index

    # ── Public API ──────────────────────────────────────────────────────

    def log_action(self, entry: ActionLogEntry) -> bool:
        """Log an autonomous action to the BM25 index.

        Returns:
            True if successfully indexed.
        """
        index = self._get_index()
        if index is None:
            _LOGGER.debug("BehavioralLog: No BM25 index available, skipping log")
            return False

        text = _format_log_text(entry)
        metadata = {
            "zone_id": entry.zone_id,
            "module_id": entry.module_id,
            "action": entry.action,
            "mood": entry.mood,
            "confidence": entry.confidence,
            "weather": entry.weather,
            "trigger": entry.trigger,
            "result": entry.result,
            "timestamp": entry.timestamp,
        }
        metadata.update(entry.details)

        try:
            from copilot_core.rag.bm25 import BM25Document
            doc = BM25Document(doc_id=entry.doc_id, text=text, metadata=metadata)
            count, errors = index.upsert_documents(
                namespace=NAMESPACE, documents=[doc],
            )
            if errors:
                _LOGGER.warning("BehavioralLog: upsert errors: %s", errors)
                return False
            self._prune()
            return count > 0
        except Exception:
            _LOGGER.exception("BehavioralLog: Failed to log action")
            return False

    def _prune(self) -> None:
        """Remove old documents exceeding retention policy.

        1. Delete documents older than RETENTION_DAYS.
        2. If total count still exceeds MAX_DOCUMENTS, delete the oldest.
        """
        index = self._get_index()
        if index is None:
            return
        try:
            conn = index._get_conn()
            cutoff = time.time() - (RETENTION_DAYS * 86400)
            # 1) Delete docs older than retention period
            conn.execute(
                "DELETE FROM bm25_docs WHERE namespace = ? AND created_at < ?",
                (NAMESPACE, cutoff),
            )
            conn.commit()
            # 2) Cap at MAX_DOCUMENTS by deleting oldest
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM bm25_docs WHERE namespace = ?",
                (NAMESPACE,),
            ).fetchone()
            total = row["cnt"] if row else 0
            if total > MAX_DOCUMENTS:
                excess = total - MAX_DOCUMENTS
                conn.execute(
                    "DELETE FROM bm25_docs WHERE namespace = ? AND doc_id IN "
                    "(SELECT doc_id FROM bm25_docs WHERE namespace = ? "
                    "ORDER BY created_at ASC LIMIT ?)",
                    (NAMESPACE, NAMESPACE, excess),
                )
                conn.commit()
                _LOGGER.debug("BehavioralLog: pruned %d excess documents", excess)
        except Exception:
            _LOGGER.debug("BehavioralLog: prune failed", exc_info=True)

    def query_history(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search autonomy history using BM25 full-text search.

        Args:
            query: Search text (e.g. "Wohnzimmer Licht").
            top_k: Max results.

        Returns:
            List of hits with text, metadata, score.
        """
        index = self._get_index()
        if index is None:
            return []

        try:
            hits = index.search(
                namespace=NAMESPACE,
                query=query,
                top_k=top_k,
                include_text=True,
                include_metadata=True,
            )
            return [
                {
                    "doc_id": h.doc_id,
                    "score": h.score,
                    "text": h.text,
                    "metadata": h.metadata,
                }
                for h in hits
            ]
        except Exception:
            _LOGGER.exception("BehavioralLog: query failed")
            return []

    def get_zone_history(
        self,
        zone_id: str,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get autonomy history for a specific zone."""
        return self.query_history(zone_id, top_k=top_k)

    def get_stats(self) -> Dict[str, Any]:
        """Return log statistics."""
        index = self._get_index()
        if index is None:
            return {"available": False}

        try:
            stats = index.stats(namespace=NAMESPACE)
            return {
                "available": True,
                "namespace": NAMESPACE,
                "doc_count": stats.doc_count,
                "avg_doc_len": stats.avg_doc_len,
                "db_size_bytes": stats.db_size_bytes,
            }
        except Exception:
            return {"available": True, "error": "stats query failed"}
