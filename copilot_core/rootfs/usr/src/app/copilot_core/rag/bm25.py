"""BM25 Index with SQLite Persistence.

Implements Okapi BM25 scoring with efficient SQLite storage for:
- Document storage with metadata
- Term frequency indexing
- Document frequency statistics
- Namespace-scoped indexes

Thread-safe with connection pooling and proper transaction handling.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

_LOGGER = logging.getLogger(__name__)

# Default storage path
DEFAULT_DB_PATH = "/data/copilot_core_rag.sqlite3"

# BM25 parameters (standard values)
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75

# Schema version for migrations
_SCHEMA_VERSION = 1

_WORD_RE = re.compile(r"\b[a-z0-9]+\b", re.IGNORECASE)


@dataclass
class BM25Document:
    """Document for BM25 indexing."""
    
    doc_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BM25Hit:
    """Search result from BM25 index."""
    
    doc_id: str
    score: float
    rank: int
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BM25Stats:
    """Statistics for a BM25 namespace."""
    
    namespace: str
    doc_count: int
    term_count: int
    posting_count: int
    avg_doc_len: float
    total_doc_len: int
    updated_at: Optional[float]
    db_path: str
    db_size_bytes: int
    schema_version: int


@dataclass
class BM25Config:
    """Configuration for BM25 index."""
    
    db_path: str = DEFAULT_DB_PATH
    k1: float = DEFAULT_K1
    b: float = DEFAULT_B
    persist: bool = True


class BM25SqliteIndex:
    """BM25 index with SQLite persistence.
    
    Features:
    - Okapi BM25 scoring
    - Namespace-scoped indexes
    - Thread-safe operations
    - Efficient term frequency storage
    - Document metadata storage
    - Statistics tracking
    
    Schema:
    - bm25_docs: Document storage
    - bm25_terms: Term-document postings
    - bm25_term_stats: Term statistics (df)
    - bm25_namespace_stats: Namespace-level statistics
    """
    
    def __init__(self, config: BM25Config | None = None) -> None:
        """Initialize the BM25 index."""
        self.config = config or BM25Config()
        self._lock = threading.RLock()
        self._local = threading.local()
        
        if self.config.persist:
            db_dir = os.path.dirname(self.config.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
        
        self._init_schema()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.config.db_path,
                timeout=30.0,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn.execute("PRAGMA synchronous = NORMAL")
            self._local.conn.execute("PRAGMA cache_size = -64000")
        return self._local.conn
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        with self._lock:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bm25_docs (
                    namespace TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    meta_json TEXT,
                    doc_len INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (namespace, doc_id)
                );
                
                CREATE TABLE IF NOT EXISTS bm25_terms (
                    namespace TEXT NOT NULL,
                    term TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    tf INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (namespace, term, doc_id)
                );
                
                CREATE TABLE IF NOT EXISTS bm25_term_stats (
                    namespace TEXT NOT NULL,
                    term TEXT NOT NULL,
                    df INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (namespace, term)
                );
                
                CREATE TABLE IF NOT EXISTS bm25_namespace_stats (
                    namespace TEXT PRIMARY KEY,
                    doc_count INTEGER NOT NULL DEFAULT 0,
                    total_doc_len INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL
                );
                
                CREATE TABLE IF NOT EXISTS bm25_schema (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_bm25_terms_lookup 
                    ON bm25_terms(namespace, term);
                
                CREATE INDEX IF NOT EXISTS idx_bm25_docs_text 
                    ON bm25_docs(namespace, doc_id);
                
                INSERT OR REPLACE INTO bm25_schema (key, value) 
                    VALUES ('schema_version', '1');
            """)
            conn.commit()
    
    def _get_namespace_stats(
        self,
        conn: sqlite3.Connection,
        *,
        namespace: str,
    ) -> Tuple[int, int, Optional[float]]:
        """Get namespace statistics."""
        row = conn.execute(
            "SELECT doc_count, total_doc_len, updated_at FROM bm25_namespace_stats WHERE namespace = ?",
            (namespace,),
        ).fetchone()
        if row is None:
            return 0, 0, None
        return int(row["doc_count"]), int(row["total_doc_len"]), float(row["updated_at"])
    
    def _get_term_dfs(
        self,
        conn: sqlite3.Connection,
        *,
        namespace: str,
        terms: Sequence[str],
    ) -> Dict[str, int]:
        """Get document frequencies for terms."""
        uniq_terms = []
        seen = set()
        for t in terms:
            if t and t not in seen:
                uniq_terms.append(t)
                seen.add(t)
        if not uniq_terms:
            return {}
        
        placeholders = ",".join(["?"] * len(uniq_terms))
        rows = conn.execute(
            "SELECT term, df FROM bm25_term_stats WHERE namespace = ? AND term IN (" + placeholders + ")",
            [namespace] + uniq_terms,
        ).fetchall()
        
        out: Dict[str, int] = {}
        for r in rows:
            out[str(r["term"])] = int(r["df"])
        return out
    
    def _get_postings(
        self,
        conn: sqlite3.Connection,
        *,
        namespace: str,
        terms: Sequence[str],
    ) -> List[Tuple[str, str, int, int]]:
        """Get postings for terms."""
        if not terms:
            return []
        
        placeholders = ",".join(["?"] * len(terms))
        sql = (
            "SELECT t.term AS term, t.doc_id AS doc_id, t.tf AS tf, d.doc_len AS doc_len "
            "FROM bm25_terms t "
            "JOIN bm25_docs d ON d.namespace = t.namespace AND d.doc_id = t.doc_id "
            "WHERE t.namespace = ? AND t.term IN (" + placeholders + ")"
        )
        rows = conn.execute(sql, [namespace] + list(terms)).fetchall()
        out: List[Tuple[str, str, int, int]] = []
        for r in rows:
            out.append((str(r["term"]), str(r["doc_id"]), int(r["tf"]), int(r["doc_len"])))
        return out
    
    def _upsert_one(
        self,
        conn: sqlite3.Connection,
        *,
        namespace: str,
        doc: BM25Document,
        now: float,
    ) -> None:
        """Upsert a single document."""
        doc_id = (doc.doc_id or "").strip()
        if not doc_id:
            raise ValueError("doc_id must be a non-empty string")
        
        text = doc.text or ""
        if not text.strip():
            raise ValueError("text must be a non-empty string")
        
        tokens = self._tokenizer(text)
        doc_len = int(len(tokens)) if tokens else 1
        tf = _term_frequencies(tokens)
        
        old = conn.execute(
            "SELECT doc_len FROM bm25_docs WHERE namespace = ? AND doc_id = ?",
            (namespace, doc_id),
        ).fetchone()
        
        if old is None:
            conn.execute(
                """
                INSERT INTO bm25_docs(namespace, doc_id, text, meta_json, doc_len, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    namespace,
                    doc_id,
                    text,
                    _json_or_none(doc.metadata),
                    doc_len,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO bm25_namespace_stats(namespace, doc_count, total_doc_len, updated_at)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(namespace) DO UPDATE SET
                    doc_count = doc_count + 1,
                    total_doc_len = total_doc_len + excluded.total_doc_len,
                    updated_at = excluded.updated_at
                """,
                (namespace, doc_len, now),
            )
        else:
            old_len = int(old["doc_len"])
            old_terms_rows = conn.execute(
                "SELECT term FROM bm25_terms WHERE namespace = ? AND doc_id = ?",
                (namespace, doc_id),
            ).fetchall()
            old_terms = [str(r["term"]) for r in old_terms_rows]
            
            if old_terms:
                for term in old_terms:
                    conn.execute(
                        "UPDATE bm25_term_stats SET df = df - 1 WHERE namespace = ? AND term = ?",
                        (namespace, term),
                    )
                    conn.execute(
                        "DELETE FROM bm25_term_stats WHERE namespace = ? AND term = ? AND df <= 0",
                        (namespace, term),
                    )
            
            conn.execute(
                "DELETE FROM bm25_terms WHERE namespace = ? AND doc_id = ?",
                (namespace, doc_id),
            )
            
            conn.execute(
                """
                INSERT INTO bm25_docs(namespace, doc_id, text, meta_json, doc_len, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, doc_id) DO UPDATE SET
                    text = excluded.text,
                    meta_json = excluded.meta_json,
                    doc_len = excluded.doc_len,
                    updated_at = excluded.updated_at
                """,
                (
                    namespace,
                    doc_id,
                    text,
                    _json_or_none(doc.metadata),
                    doc_len,
                    now,
                    now,
                ),
            )
            
            delta = int(doc_len - old_len)
            conn.execute(
                """
                INSERT INTO bm25_namespace_stats(namespace, doc_count, total_doc_len, updated_at)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(namespace) DO UPDATE SET
                    total_doc_len = total_doc_len + ?,
                    updated_at = excluded.updated_at
                """,
                (namespace, doc_len, now, delta),
            )
        
        if tf:
            for term, count in tf.items():
                conn.execute(
                    "INSERT INTO bm25_terms(namespace, term, doc_id, tf) VALUES (?, ?, ?, ?)",
                    (namespace, term, doc_id, int(count)),
                )
                conn.execute(
                    """
                    INSERT INTO bm25_term_stats(namespace, term, df)
                    VALUES (?, ?, 1)
                    ON CONFLICT(namespace, term) DO UPDATE SET df = df + 1
                    """,
                    (namespace, term),
                )
    
    def upsert_documents(
        self,
        *,
        namespace: str,
        documents: Sequence[BM25Document],
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Upsert multiple documents.
        
        Returns:
            Tuple of (success_count, error_list)
        """
        if not documents:
            return 0, []
        
        conn = self._get_conn()
        errors: List[Dict[str, Any]] = []
        success_count = 0
        now = datetime.now(timezone.utc).timestamp()
        
        with self._lock:
            for i, doc in enumerate(documents):
                try:
                    self._upsert_one(conn, namespace=namespace, doc=doc, now=now)
                    success_count += 1
                except Exception as e:
                    errors.append({
                        "index": i,
                        "doc_id": getattr(doc, 'doc_id', f'index_{i}'),
                        "error": str(e),
                    })
            conn.commit()
        
        return success_count, errors
    
    def search(
        self,
        *,
        namespace: str,
        query: str,
        top_k: int = 10,
        include_text: bool = False,
        include_metadata: bool = False,
    ) -> List[BM25Hit]:
        """Search documents using BM25 scoring."""
        if top_k <= 0:
            return []
        
        conn = self._get_conn()
        tokens = self._tokenizer(query)
        
        if not tokens:
            return []
        
        with self._lock:
            doc_count, total_doc_len, _ = self._get_namespace_stats(conn, namespace=namespace)
            if doc_count == 0:
                return []
            
            avg_doc_len = total_doc_len / doc_count if doc_count > 0 else 1.0
            term_dfs = self._get_term_dfs(conn, namespace=namespace, terms=tokens)
            postings = self._get_postings(conn, namespace=namespace, terms=tokens)
        
        doc_scores: Dict[str, float] = {}
        doc_lens: Dict[str, int] = {}
        
        for term, doc_id, tf, doc_len in postings:
            df = term_dfs.get(term, 0)
            idf = _bm25_idf(n=doc_count, df=df)
            term_score = _bm25_term_score(
                idf=idf,
                tf=tf,
                doc_len=doc_len,
                avg_doc_len=avg_doc_len,
                k1=self.config.k1,
                b=self.config.b,
            )
            
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + term_score
            doc_lens[doc_id] = doc_len
        
        ranked = sorted(doc_scores.items(), key=lambda x: (-x[1], x[0]))[:top_k]
        
        hits: List[BM25Hit] = []
        for rank, (doc_id, score) in enumerate(ranked, start=1):
            hit = BM25Hit(doc_id=doc_id, score=score, rank=rank)
            
            if include_text or include_metadata:
                doc_row = conn.execute(
                    "SELECT text, meta_json FROM bm25_docs WHERE namespace = ? AND doc_id = ?",
                    (namespace, doc_id),
                ).fetchone()
                if doc_row:
                    if include_text:
                        hit.text = doc_row["text"]
                    if include_metadata:
                        hit.metadata = _parse_json(doc_row["meta_json"])
            
            hits.append(hit)
        
        return hits
    
    def get_documents(
        self,
        *,
        namespace: str,
        doc_ids: Sequence[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Get documents by IDs."""
        if not doc_ids:
            return {}
        
        conn = self._get_conn()
        placeholders = ",".join(["?"] * len(doc_ids))
        rows = conn.execute(
            f"SELECT doc_id, text, meta_json FROM bm25_docs WHERE namespace = ? AND doc_id IN ({placeholders})",
            [namespace] + list(doc_ids),
        ).fetchall()
        
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            doc_id = str(row["doc_id"])
            result[doc_id] = {
                "text": row["text"],
                "metadata": _parse_json(row["meta_json"]),
            }
        
        return result
    
    def stats(self, *, namespace: str) -> BM25Stats:
        """Get index statistics."""
        conn = self._get_conn()
        
        with self._lock:
            doc_count, total_doc_len, updated_at = self._get_namespace_stats(conn, namespace=namespace)
            
            term_count = conn.execute(
                "SELECT COUNT(*) FROM bm25_term_stats WHERE namespace = ?",
                (namespace,),
            ).fetchone()[0]
            
            posting_count = conn.execute(
                "SELECT COUNT(*) FROM bm25_terms WHERE namespace = ?",
                (namespace,),
            ).fetchone()[0]
            
            db_size_bytes = 0
            if self.config.persist and os.path.exists(self.config.db_path):
                db_size_bytes = os.path.getsize(self.config.db_path)
            
            avg_doc_len = total_doc_len / doc_count if doc_count > 0 else 0.0
        
        return BM25Stats(
            namespace=namespace,
            doc_count=doc_count,
            term_count=term_count,
            posting_count=posting_count,
            avg_doc_len=avg_doc_len,
            total_doc_len=total_doc_len,
            updated_at=updated_at,
            db_path=self.config.db_path,
            db_size_bytes=db_size_bytes,
            schema_version=_SCHEMA_VERSION,
        )
    
    def _tokenizer(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        return default_tokenize(text)
    
    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None


def default_tokenize(text: str) -> List[str]:
    """Default tokenizer: lowercase alphanumeric words."""
    return _WORD_RE.findall((text or "").lower())


def _term_frequencies(tokens: Iterable[str]) -> Dict[str, int]:
    """Calculate term frequencies."""
    tf: Dict[str, int] = {}
    for t in tokens:
        if not t:
            continue
        tf[t] = tf.get(t, 0) + 1
    return tf


def _json_or_none(metadata: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Serialize metadata to JSON."""
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        try:
            return json.dumps(dict(metadata), ensure_ascii=False, separators=(",", ":"), default=str)
        except Exception:
            return None


def _parse_json(json_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse JSON string."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except Exception:
        return None


def _bm25_idf(*, n: int, df: int) -> float:
    """Calculate BM25 IDF."""
    if n <= 0 or df <= 0:
        return 0.0
    return math.log(((n - df + 0.5) / (df + 0.5)) + 1.0)


def _bm25_term_score(
    *,
    idf: float,
    tf: int,
    doc_len: int,
    avg_doc_len: float,
    k1: float,
    b: float,
) -> float:
    """Calculate BM25 term score."""
    if tf <= 0:
        return 0.0
    dl = float(max(1, doc_len))
    avgdl = float(avg_doc_len) if avg_doc_len > 0.0 else 1.0
    denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
    if denom <= 0.0:
        return 0.0
    return float(idf) * (float(tf) * (k1 + 1.0)) / denom
<<<<<<< HEAD

# Alias for backwards compatibility with tests
=======
# Backwards compatibility alias
>>>>>>> ed83058e (fix(rag): BM25Index alias + remove spurious -e in bm25.py)
BM25Index = BM25SqliteIndex
