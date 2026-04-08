"""
Pattern Library -- Collectively learned patterns from federated homes.

Stores anonymized patterns shared across homes via the federated
learning protocol. Patterns are scored by collective confidence.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("PATTERN_LIBRARY_DB", "/data/pattern_library.db")


class PatternLibrary:
    """Shared pattern store for collectively learned home-automation rules.

    Patterns represent antecedent-consequent relationships discovered
    across multiple homes.  Each pattern carries a *collective confidence*
    score that increases as more homes confirm it.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        logger.info("PatternLibrary initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS patterns (
                        id                    TEXT PRIMARY KEY,
                        pattern_type          TEXT NOT NULL,
                        antecedent            TEXT NOT NULL,
                        consequent            TEXT NOT NULL,
                        collective_confidence REAL NOT NULL DEFAULT 0.0,
                        homes_count           INTEGER NOT NULL DEFAULT 1,
                        created_at            TEXT NOT NULL,
                        updated_at            TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_patterns_type
                        ON patterns(pattern_type);
                    CREATE INDEX IF NOT EXISTS idx_patterns_confidence
                        ON patterns(collective_confidence DESC);
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _pattern_fingerprint(
        pattern_type: str, antecedent: str, consequent: str
    ) -> str:
        """Deterministic id derived from content so duplicates merge."""
        raw = f"{pattern_type}|{antecedent}|{consequent}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_pattern(
        self,
        pattern_type: str,
        antecedent: str,
        consequent: str,
        confidence: float,
        source_home_hash: str,
    ) -> str:
        """Add or update a pattern.

        If a pattern with the same fingerprint already exists, its
        confidence is merged (weighted average) and ``homes_count``
        incremented.

        Returns the pattern id.
        """
        pid = self._pattern_fingerprint(pattern_type, antecedent, consequent)
        now = self._now_iso()

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT collective_confidence, homes_count FROM patterns "
                    "WHERE id = ?",
                    (pid,),
                ).fetchone()

                if row:
                    old_conf, homes = row
                    # Weighted merge: existing data has more weight
                    new_conf = (old_conf * homes + confidence) / (homes + 1)
                    conn.execute(
                        "UPDATE patterns SET collective_confidence = ?, "
                        "homes_count = ?, updated_at = ? WHERE id = ?",
                        (round(new_conf, 6), homes + 1, now, pid),
                    )
                else:
                    conn.execute(
                        "INSERT INTO patterns "
                        "(id, pattern_type, antecedent, consequent, "
                        "collective_confidence, homes_count, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                        (pid, pattern_type, antecedent, consequent,
                         round(confidence, 6), now, now),
                    )

                conn.commit()
            finally:
                conn.close()

        logger.debug(
            "Pattern %s added/updated (type=%s, home=%s)",
            pid, pattern_type, source_home_hash,
        )
        return pid

    def get_applicable_patterns(
        self, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Return patterns whose antecedent matches *context*.

        Matching is done by checking whether the antecedent string
        (stored as JSON or plain text) is a substring of the serialised
        context, or shares entity ids with it.
        """
        context_str = json.dumps(context).lower()
        entity_ids: set[str] = set()
        for key in ("entity_id", "entity_ids", "entities"):
            val = context.get(key)
            if isinstance(val, str):
                entity_ids.add(val)
            elif isinstance(val, list):
                entity_ids.update(val)

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT id, pattern_type, antecedent, consequent, "
                    "collective_confidence, homes_count, created_at, updated_at "
                    "FROM patterns ORDER BY collective_confidence DESC"
                ).fetchall()
            finally:
                conn.close()

        matches: list[dict] = []
        for row in rows:
            antecedent_lower = row[2].lower()
            # Match by substring or entity overlap
            if antecedent_lower in context_str or any(
                eid in antecedent_lower for eid in entity_ids
            ):
                matches.append(self._row_to_dict(row))

        return matches

    def merge_remote_patterns(self, patterns: List[Dict[str, Any]]) -> int:
        """Merge a batch of patterns received from federated sync.

        Each entry must have: ``pattern_type``, ``antecedent``,
        ``consequent``, ``confidence``, ``source_home_hash``.

        Returns the number of patterns merged.
        """
        merged = 0
        for p in patterns:
            try:
                self.add_pattern(
                    pattern_type=p["pattern_type"],
                    antecedent=p["antecedent"],
                    consequent=p["consequent"],
                    confidence=p.get("confidence", 0.5),
                    source_home_hash=p.get("source_home_hash", "unknown"),
                )
                merged += 1
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed remote pattern: %s", exc)
        logger.info("Merged %d / %d remote patterns", merged, len(patterns))
        return merged

    def get_top_patterns(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the top patterns ranked by collective confidence."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT id, pattern_type, antecedent, consequent, "
                    "collective_confidence, homes_count, created_at, updated_at "
                    "FROM patterns ORDER BY collective_confidence DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()

        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Row mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "pattern_type": row[1],
            "antecedent": row[2],
            "consequent": row[3],
            "collective_confidence": row[4],
            "homes_count": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
