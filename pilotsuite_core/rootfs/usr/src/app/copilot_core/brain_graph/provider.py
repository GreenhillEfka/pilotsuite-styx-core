from __future__ import annotations

import threading

from flask import current_app

from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.brain_graph.store import BrainGraphStore

# Process-wide singleton. This keeps the in-memory graph consistent between
# /api/v1/graph/* and ingest-time feeding in /api/v1/events.
_STORE: BrainGraphStore | None = None
_SVC: BrainGraphService | None = None
_LOCK = threading.Lock()


def get_graph_service() -> BrainGraphService:
    global _STORE, _SVC
    if _SVC is not None:
        return _SVC

    with _LOCK:
        # Double-checked locking
        if _SVC is not None:
            return _SVC

        cfg = current_app.config.get("COPILOT_CFG")
        data_dir = str(getattr(cfg, "data_dir", "/data"))
        db_path = str(getattr(cfg, "brain_graph_json_path", f"{data_dir}/brain_graph.db"))
        nodes_max = int(getattr(cfg, "brain_graph_nodes_max", 500))
        edges_max = int(getattr(cfg, "brain_graph_edges_max", 1500))

        _STORE = BrainGraphStore(
            db_path=db_path,
            max_nodes=nodes_max,
            max_edges=edges_max,
            node_min_score=0.1,
            edge_min_weight=0.1
        )
        _SVC = BrainGraphService(_STORE)
        return _SVC
