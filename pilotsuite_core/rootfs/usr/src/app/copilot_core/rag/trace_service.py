"""RAG Trace Timeline Service (Slice 150).

End-to-end trace tracking for RAG queries with timeline visualization.
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# In-memory trace storage (replace with DB in production)
_traces: Dict[str, Dict[str, Any]] = {}
_trace_history: deque[str] = deque(maxlen=1000)


@dataclass
class TraceStage:
    stage_id: str
    name: str
    status: str  # pending, running, complete, error
    started_at: str
    completed_at: Optional[str] = None
    latency_ms: float = 0.0
    kpi: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGTrace:
    trace_id: str
    input_id: str
    query: str
    stages: List[TraceStage]
    total_latency_ms: float
    status: str
    created_at: str
    links: Dict[str, str] = field(default_factory=dict)


def create_trace(query: str) -> str:
    """Create a new RAG trace."""
    trace_id = str(uuid.uuid4())[:8]
    input_id = str(uuid.uuid4())[:8]
    
    trace = {
        "trace_id": trace_id,
        "input_id": input_id,
        "query": query,
        "stages": [],
        "total_latency_ms": 0.0,
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "links": {
            "dashboard_kpi": f"/api/v1/backend_ui/dashboard?highlight={trace_id}",
            "zone_map_link": f"/api/v1/backend_ui/zones?trace={trace_id}",
        },
    }
    
    _traces[trace_id] = trace
    _trace_history.append(trace_id)
    
    return trace_id


def add_stage(trace_id: str, stage_name: str, status: str = "running") -> str:
    """Add a stage to a trace."""
    if trace_id not in _traces:
        raise ValueError(f"Trace {trace_id} not found")
    
    stage_id = str(uuid.uuid4())[:8]
    stage = {
        "stage_id": stage_id,
        "name": stage_name,
        "status": status,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "latency_ms": 0.0,
        "kpi": {},
    }
    
    _traces[trace_id]["stages"].append(stage)
    
    return stage_id


def complete_stage(trace_id: str, stage_id: str, kpi: Dict[str, Any] = None):
    """Mark a stage as complete."""
    if trace_id not in _traces:
        return
    
    trace = _traces[trace_id]
    for stage in trace["stages"]:
        if stage["stage_id"] == stage_id:
            stage["status"] = "complete"
            stage["completed_at"] = datetime.now(timezone.utc).isoformat()
            stage["latency_ms"] = _calculate_latency(
                stage["started_at"], stage["completed_at"]
            )
            if kpi:
                stage["kpi"] = kpi
            break


def complete_trace(trace_id: str, status: str = "complete"):
    """Mark a trace as complete."""
    if trace_id not in _traces:
        return
    
    trace = _traces[trace_id]
    trace["status"] = status
    
    # Calculate total latency
    total_latency = sum(s.get("latency_ms", 0) for s in trace["stages"])
    trace["total_latency_ms"] = total_latency


def _calculate_latency(started_at: str, completed_at: str) -> float:
    """Calculate latency between two timestamps."""
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        return (end - start).total_seconds() * 1000
    except:
        return 0.0


def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific trace."""
    return _traces.get(trace_id)


def get_recent_traces(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent traces in reverse chronological order."""
    recent_ids = list(_trace_history)[-limit:]
    return [_traces[tid] for tid in reversed(recent_ids) if tid in _traces]


def get_activity_summary() -> Dict[str, Any]:
    """Get summary of recent activity."""
    now = datetime.now(timezone.utc)
    recent_traces = get_recent_traces(100)
    
    return {
        "total_traces": len(_traces),
        "recent_count": len(recent_traces),
        "avg_latency_ms": sum(t["total_latency_ms"] for t in recent_traces) / max(len(recent_traces), 1),
        "success_rate": sum(1 for t in recent_traces if t["status"] == "complete") / max(len(recent_traces), 1),
        "generated_at": now.isoformat(),
    }
