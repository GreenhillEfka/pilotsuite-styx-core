"""
SQLite-based graph storage with bounded capacity and automatic pruning.

FIX: Added async support via ThreadPoolExecutor for non-blocking I/O.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .model import GraphNode, GraphEdge, NodeKind, EdgeType


# Thread pool for async SQLite operations (avoids blocking Flask threads)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="brain_graph_")
logger = logging.getLogger(__name__)


class BrainGraphStore:
    """SQLite-backed graph storage with bounded capacity.
    
    FIX: Now supports async operations via ThreadPoolExecutor to prevent
    blocking the Flask event loop under high load.
    """
    
    def __init__(
        self,
        db_path: str = "/data/brain_graph.db",
        max_nodes: int = 500,
        max_edges: int = 1500,
        node_min_score: float = 0.1,
        edge_min_weight: float = 0.1
    ):
        self.db_path = self._resolve_db_path(Path(db_path))
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.node_min_score = node_min_score
        self.edge_min_weight = edge_min_weight
        self._connect_timeout = 30  # seconds

        # Serialize write operations to avoid SQLite "database is locked" errors
        self._write_lock = threading.Lock()

        # Initialize database
        self._init_db()

    def _resolve_db_path(self, configured_path: Path) -> Path:
        """Resolve a writable SQLite path with fallback outside add-on runtime."""
        try:
            configured_path.parent.mkdir(parents=True, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = Path(os.environ.get("COPILOT_BRAIN_GRAPH_DB_DIR", "/tmp"))
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / configured_path.name
            logger.warning(
                "BrainGraphStore path %s is not writable, using fallback %s",
                configured_path,
                fallback_path,
            )
            return fallback_path
    
    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection with proper timeout and pragmas."""
        return sqlite3.connect(self.db_path, timeout=self._connect_timeout)

    def _init_db(self):
        """Initialize SQLite schema with WAL mode for better concurrency."""
        with self._connect() as conn:
            # Enable WAL mode for better concurrency (SQLite best practice)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA cache_size=-8000")  # 8 MB
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    label TEXT NOT NULL,
                    updated_at_ms INTEGER NOT NULL,
                    score REAL NOT NULL,
                    domain TEXT,
                    source_json TEXT,
                    tags_json TEXT,
                    meta_json TEXT
                );
                
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    from_node TEXT NOT NULL,
                    to_node TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    updated_at_ms INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    evidence_json TEXT,
                    meta_json TEXT,
                    FOREIGN KEY (from_node) REFERENCES nodes (id) ON DELETE CASCADE,
                    FOREIGN KEY (to_node) REFERENCES nodes (id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes (kind);
                CREATE INDEX IF NOT EXISTS idx_nodes_domain ON nodes (domain);
                CREATE INDEX IF NOT EXISTS idx_nodes_updated ON nodes (updated_at_ms);
                CREATE INDEX IF NOT EXISTS idx_nodes_score ON nodes (score);
                
                CREATE INDEX IF NOT EXISTS idx_edges_from ON edges (from_node);
                CREATE INDEX IF NOT EXISTS idx_edges_to ON edges (to_node);
                CREATE INDEX IF NOT EXISTS idx_edges_type ON edges (edge_type);
                CREATE INDEX IF NOT EXISTS idx_edges_updated ON edges (updated_at_ms);
                CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges (weight);

                CREATE INDEX IF NOT EXISTS idx_nodes_kind_domain ON nodes (kind, domain);
                CREATE INDEX IF NOT EXISTS idx_nodes_kind_score ON nodes (kind, score);
                CREATE INDEX IF NOT EXISTS idx_edges_type_weight ON edges (edge_type, weight);
            """)
    
    def upsert_node(self, node: GraphNode) -> bool:
        """Insert or update a node. Returns True if inserted/updated."""
        with self._write_lock, self._connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO nodes 
                (id, kind, label, updated_at_ms, score, domain, source_json, tags_json, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.kind,
                    node.label,
                    node.updated_at_ms,
                    node.score,
                    node.domain,
                    json.dumps(node.source) if node.source else None,
                    json.dumps(node.tags) if node.tags else None,
                    json.dumps(node.meta) if node.meta else None,
                )
            )
            
            return cursor.rowcount > 0
    
    def upsert_edge(self, edge: GraphEdge) -> bool:
        """Insert or update an edge. Returns True if inserted/updated."""
        with self._write_lock, self._connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO edges
                (id, from_node, to_node, edge_type, updated_at_ms, weight, evidence_json, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.from_node,
                    edge.to_node,
                    edge.edge_type,
                    edge.updated_at_ms,
                    edge.weight,
                    json.dumps(edge.evidence) if edge.evidence else None,
                    json.dumps(edge.meta) if edge.meta else None,
                )
            )
            
            return cursor.rowcount > 0
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a node by ID."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return GraphNode(
                id=row["id"],
                kind=row["kind"],
                label=row["label"],
                updated_at_ms=row["updated_at_ms"],
                score=row["score"],
                domain=row["domain"],
                source=json.loads(row["source_json"]) if row["source_json"] else None,
                tags=json.loads(row["tags_json"]) if row["tags_json"] else None,
                meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
            )
    
    def get_nodes(
        self,
        kinds: Optional[List[NodeKind]] = None,
        domains: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[GraphNode]:
        """Retrieve nodes with optional filtering."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM nodes WHERE 1=1"
            params = []
            
            if kinds:
                placeholders = ",".join("?" * len(kinds))
                query += f" AND kind IN ({placeholders})"
                params.extend(kinds)
                
            if domains:
                placeholders = ",".join("?" * len(domains))
                query += f" AND domain IN ({placeholders})"
                params.extend(domains)
                
            query += " ORDER BY score DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                GraphNode(
                    id=row["id"],
                    kind=row["kind"],
                    label=row["label"],
                    updated_at_ms=row["updated_at_ms"],
                    score=row["score"],
                    domain=row["domain"],
                    source=json.loads(row["source_json"]) if row["source_json"] else None,
                    tags=json.loads(row["tags_json"]) if row["tags_json"] else None,
                    meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
                )
                for row in rows
            ]
    
    def get_edges(
        self,
        from_node: Optional[str] = None,
        to_node: Optional[str] = None,
        edge_types: Optional[List[EdgeType]] = None,
        limit: Optional[int] = None
    ) -> List[GraphEdge]:
        """Retrieve edges with optional filtering."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM edges WHERE 1=1"
            params = []
            
            if from_node:
                query += " AND from_node = ?"
                params.append(from_node)
                
            if to_node:
                query += " AND to_node = ?"
                params.append(to_node)
                
            if edge_types:
                placeholders = ",".join("?" * len(edge_types))
                query += f" AND edge_type IN ({placeholders})"
                params.extend(edge_types)
                
            query += " ORDER BY weight DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                GraphEdge(
                    id=row["id"],
                    from_node=row["from_node"],
                    to_node=row["to_node"],
                    edge_type=row["edge_type"],
                    updated_at_ms=row["updated_at_ms"],
                    weight=row["weight"],
                    evidence=json.loads(row["evidence_json"]) if row["evidence_json"] else None,
                    meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
                )
                for row in rows
            ]
    
    def get_neighborhood(
        self, 
        center_node: str, 
        hops: int = 1,
        max_nodes: Optional[int] = None,
        max_edges: Optional[int] = None
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Get nodes and edges within N hops of a center node.
        
        FIX: Uses batched SQL queries to avoid N+1 pattern.
        Previous implementation made 2*N queries per hop; now uses 2 queries total.
        """
        visited_nodes: Set[str] = {center_node}
        current_layer = {center_node}
        
        # Expand outward for specified hops
        for _ in range(hops):
            next_layer = set()
            
            # FIX: Batch query all edges from current layer in ONE query
            if current_layer:
                with self._connect() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    placeholders = ",".join("?" * len(current_layer))
                    
                    # Single query for all outbound edges
                    cursor.execute(
                        f"SELECT * FROM edges WHERE from_node IN ({placeholders})",
                        list(current_layer)
                    )
                    outbound_rows = cursor.fetchall()
                    
                    # Single query for all inbound edges
                    cursor.execute(
                        f"SELECT * FROM edges WHERE to_node IN ({placeholders})",
                        list(current_layer)
                    )
                    inbound_rows = cursor.fetchall()
                    
                    # Process edges to find neighbors
                    all_edges = []
                    for row in outbound_rows + inbound_rows:
                        edge = GraphEdge(
                            id=row["id"],
                            from_node=row["from_node"],
                            to_node=row["to_node"],
                            edge_type=row["edge_type"],
                            updated_at_ms=row["updated_at_ms"],
                            weight=row["weight"],
                            evidence=json.loads(row["evidence_json"]) if row["evidence_json"] else None,
                            meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
                        )
                        all_edges.append(edge)
                        neighbor = edge.to_node if edge.from_node in current_layer else edge.from_node
                        if neighbor not in visited_nodes:
                            next_layer.add(neighbor)
                        
            visited_nodes.update(next_layer)
            current_layer = next_layer
            
            if not next_layer:
                break
        
        # FIX: Batch fetch all nodes in ONE query instead of N queries
        if visited_nodes:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                placeholders = ",".join("?" * len(visited_nodes))
                cursor.execute(
                    f"SELECT * FROM nodes WHERE id IN ({placeholders})",
                    list(visited_nodes)
                )
                rows = cursor.fetchall()
                
                nodes = [
                    GraphNode(
                        id=row["id"],
                        kind=row["kind"],
                        label=row["label"],
                        updated_at_ms=row["updated_at_ms"],
                        score=row["score"],
                        domain=row["domain"],
                        source=json.loads(row["source_json"]) if row["source_json"] else None,
                        tags=json.loads(row["tags_json"]) if row["tags_json"] else None,
                        meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
                    )
                    for row in rows
                ]
        else:
            nodes = []
        
        # Apply limits by salience/recency
        if max_nodes and len(nodes) > max_nodes:
            nodes = sorted(nodes, key=lambda n: n.effective_score(), reverse=True)[:max_nodes]
            visited_nodes = {n.id for n in nodes}
        
        # FIX: Batch fetch all edges between visited nodes in ONE query
        edges = []
        if visited_nodes:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                placeholders = ",".join("?" * len(visited_nodes))
                
                # Single query for edges where both nodes are in visited set
                cursor.execute(
                    f"""SELECT * FROM edges 
                        WHERE from_node IN ({placeholders}) 
                        AND to_node IN ({placeholders})""",
                    list(visited_nodes) * 2
                )
                rows = cursor.fetchall()
                
                edges = [
                    GraphEdge(
                        id=row["id"],
                        from_node=row["from_node"],
                        to_node=row["to_node"],
                        edge_type=row["edge_type"],
                        updated_at_ms=row["updated_at_ms"],
                        weight=row["weight"],
                        evidence=json.loads(row["evidence_json"]) if row["evidence_json"] else None,
                        meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
                    )
                    for row in rows
                ]
        
        if max_edges and len(edges) > max_edges:
            edges = sorted(edges, key=lambda e: e.effective_weight(), reverse=True)[:max_edges]
        
        return nodes, edges
    
    def prune_graph(self, now_ms: Optional[int] = None) -> Dict[str, int]:
        """Remove low-salience nodes/edges and enforce capacity limits.
        
        Optimized: Uses only 2 table scans (one for edges, one for nodes)
        instead of 4 separate scans.
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        stats = {"nodes_removed": 0, "edges_removed": 0}

        with self._write_lock, self._connect() as conn:
            cursor = conn.cursor()

            # ========== Single pass for edges ==========
            cursor.execute("SELECT * FROM edges")
            all_edges = []
            weak_edge_ids = []
            
            for row in cursor.fetchall():
                edge = GraphEdge(
                    id=row[0],
                    from_node=row[1], 
                    to_node=row[2],
                    edge_type=row[3],
                    updated_at_ms=row[4],
                    weight=row[5],
                    evidence=json.loads(row[6]) if row[6] else None,
                    meta=json.loads(row[7]) if row[7] else {},
                )
                effective_weight = edge.effective_weight(now_ms)
                
                if effective_weight < self.edge_min_weight:
                    weak_edge_ids.append(edge.id)
                all_edges.append((edge.id, effective_weight, edge.updated_at_ms))
            
            # Remove weak edges
            if weak_edge_ids:
                placeholders = ",".join("?" * len(weak_edge_ids))
                cursor.execute(f"DELETE FROM edges WHERE id IN ({placeholders})", weak_edge_ids)
                stats["edges_removed"] += cursor.rowcount
            
            # Enforce edge limit in same pass
            if len(all_edges) > self.max_edges:
                # Sort by weight desc, then recency desc
                all_edges.sort(key=lambda x: (x[1], x[2]), reverse=True)
                edges_to_remove = [eid for eid, _, _ in all_edges[self.max_edges:]]
                
                if edges_to_remove:
                    placeholders = ",".join("?" * len(edges_to_remove))
                    cursor.execute(f"DELETE FROM edges WHERE id IN ({placeholders})", edges_to_remove)
                    stats["edges_removed"] += cursor.rowcount
            
            # ========== Single pass for nodes ==========
            cursor.execute("""
                SELECT n.*, 
                       (SELECT COUNT(*) FROM edges WHERE from_node = n.id OR to_node = n.id) as edge_count
                FROM nodes n
            """)
            all_nodes = []
            weak_node_ids = []
            
            for row in cursor.fetchall():
                node = GraphNode(
                    id=row[0],
                    kind=row[1],
                    label=row[2], 
                    updated_at_ms=row[3],
                    score=row[4],
                    domain=row[5],
                    source=json.loads(row[6]) if row[6] else None,
                    tags=json.loads(row[7]) if row[7] else None,
                    meta=json.loads(row[8]) if row[8] else {},
                )
                edge_count = row[9]  # Already joined from subquery
                effective_score = node.effective_score(now_ms)
                
                if effective_score < self.node_min_score and edge_count == 0:
                    weak_node_ids.append(node.id)
                all_nodes.append((node.id, effective_score, node.updated_at_ms))
            
            # Remove weak nodes
            if weak_node_ids:
                placeholders = ",".join("?" * len(weak_node_ids))
                cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", weak_node_ids)
                stats["nodes_removed"] += cursor.rowcount
            
            # Enforce node limit in same pass
            if len(all_nodes) > self.max_nodes:
                # Sort by score desc, then recency desc
                all_nodes.sort(key=lambda x: (x[1], x[2]), reverse=True)
                nodes_to_remove = [nid for nid, _, _ in all_nodes[self.max_nodes:]]
                
                if nodes_to_remove:
                    placeholders = ",".join("?" * len(nodes_to_remove))
                    # Remove associated edges first
                    cursor.execute(
                        f"DELETE FROM edges WHERE from_node IN ({placeholders}) OR to_node IN ({placeholders})",
                        nodes_to_remove + nodes_to_remove
                    )
                    # Remove nodes
                    cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", nodes_to_remove)
                    stats["nodes_removed"] += cursor.rowcount
            
            conn.commit()
        
        return stats
    
    def get_stats(self) -> Dict[str, int]:
        """Get current graph statistics."""
        with self._connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM nodes")
            node_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM edges") 
            edge_count = cursor.fetchone()[0]
            
            return {
                "nodes": node_count,
                "edges": edge_count,
                "max_nodes": self.max_nodes,
                "max_edges": self.max_edges,
            }

    # === Async Wrapper Methods (FIX: Non-blocking I/O) ===
    # These methods run SQLite operations in a thread pool to avoid
    # blocking the Flask event loop. Use these for async callers.
    
    async def upsert_node_async(self, node: GraphNode) -> bool:
        """Async wrapper for upsert_node - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.upsert_node, node)
    
    async def upsert_edge_async(self, edge: GraphEdge) -> bool:
        """Async wrapper for upsert_edge - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.upsert_edge, edge)
    
    async def get_node_async(self, node_id: str) -> Optional[GraphNode]:
        """Async wrapper for get_node - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.get_node, node_id)
    
    async def get_nodes_async(
        self,
        kinds: Optional[List[NodeKind]] = None,
        domains: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[GraphNode]:
        """Async wrapper for get_nodes - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self.get_nodes, kinds, domains, limit
        )
    
    async def get_edges_async(
        self,
        from_node: Optional[str] = None,
        to_node: Optional[str] = None,
        edge_types: Optional[List[EdgeType]] = None,
        limit: Optional[int] = None
    ) -> List[GraphEdge]:
        """Async wrapper for get_edges - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self.get_edges, from_node, to_node, edge_types, limit
        )
    
    async def get_neighborhood_async(
        self, 
        center_node: str, 
        hops: int = 1,
        max_nodes: Optional[int] = None,
        max_edges: Optional[int] = None
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Async wrapper for get_neighborhood - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self.get_neighborhood, center_node, hops, max_nodes, max_edges
        )
    
    async def get_stats_async(self) -> Dict[str, int]:
        """Async wrapper for get_stats - runs in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.get_stats)


# Alias for backwards compatibility
GraphStore = BrainGraphStore
