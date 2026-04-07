"""RAG Trace Timeline API (Slice 150/166 Massive Expansion).

Implements end-to-end tracing for RAG pipeline stages:
1. Query Parsing
2. Context Retrieval (Local + Web)
3. Embedding Search
4. LLM Generation
5. Post-Processing
"""

from __future__ import annotations

import logging
import time
import uuid
from flask import Blueprint, jsonify
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

rag_trace_bp = Blueprint("rag_trace", __name__, url_prefix="/api/v1/rag")

class RAGTraceSession:
    """Represents a single RAG request trace."""
    
    def __init__(self, query: str):
        self.trace_id = str(uuid.uuid4())
        self.query = query
        self.start_time = time.perf_counter()
        self.stages: List[Dict[str, Any]] = []

    def log_stage(self, stage_name: str, status: str = "ok"):
        """Logs completion of a pipeline stage."""
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.stages.append({
            "stage": stage_name,
            "ts_ms": round(elapsed, 2),
            "status": status
        })

# Global Traces (Memory Cache for UI)
_traces: Dict[str, RAGTraceSession] = {}

@rag_trace_bp.route("/traces", methods=["GET"])
def get_traces():
    """Returns recent RAG traces for the timeline UI."""
    return jsonify({
        "ok": True,
        "traces": [
            {
                "id": t.trace_id,
                "query": t.query,
                "total_ms": t.stages[-1]["ts_ms"] if t.stages else 0,
                "stages": t.stages
            } for t in list(_traces.values())[-10:] # Last 10
        ]
    })

@rag_trace_bp.route("/traces/<trace_id>", methods=["GET"])
def get_trace_detail(trace_id: str):
    """Returns detailed stage-by-stage latency for a trace."""
    trace = _traces.get(trace_id)
    if not trace:
        return jsonify({"ok": False, "error": "trace_not_found"}), 404
    return jsonify({"ok": True, "trace": trace.__dict__})

# Helper for expansion workers
def create_mock_trace(query: str):
    session = RAGTraceSession(query)
    session.log_stage("query_parsing")
    time.sleep(0.01)
    session.log_stage("vector_search")
    time.sleep(0.05)
    session.log_stage("web_search_searxng")
    time.sleep(0.08)
    session.log_stage("llm_generation")
    _traces[session.trace_id] = session
    return session.trace_id
