"""
Brain Growth Read Model — Inspizierbarer Snapshot von Brain + Neuronen + Modul-Context.

Frei nach: "Slice 5 — Brain Growth Unification (P1)"
Goal: Semantischer Transfer in Graph + Neuron + Modul-Context explizit und inspizierbar.

Liefert:
  - BrainActivitySnapshot: aktive Neuronen, Brain-Graph-Wachstum (neue Kanten/Knoten),
    letzte Ereignisse
  - get_brain_summary(): fasst Brain Graph + Neuron States + Module-Context zusammen

Dieses Read Model wird von api/v1/ als Read Model exponiert und kann von
ingest/event_processor.py über feed_brain(event) gefüllt werden.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class BrainGraphGrowth:
    """Brain Graph Wachstum seit letztem Snapshot."""

    total_nodes: int = 0
    total_edges: int = 0
    new_nodes_since_last: int = 0
    new_edges_since_last: int = 0
    nodes_by_kind: Dict[str, int] = field(default_factory=dict)
    edges_by_type: Dict[str, int] = field(default_factory=dict)
    top_active_nodes: List[Dict[str, Any]] = field(default_factory=list)
    graph_version: int = 0


@dataclass
class NeuronSnapshot:
    """Zustand eines einzelnen Neurons für das Read Model."""

    name: str
    neuron_type: str          # context | state | mood
    value: float
    active: bool
    confidence: float
    last_update: Optional[str] = None
    last_trigger: Optional[str] = None
    trigger_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.neuron_type,
            "value": round(self.value, 3),
            "active": self.active,
            "confidence": round(self.confidence, 3),
            "last_update": self.last_update,
            "last_trigger": self.last_trigger,
            "trigger_count": self.trigger_count,
        }


@dataclass
class BrainActivitySnapshot:
    """
    Vollständiger Brain Activity Snapshot.

    Enthält:
      - graph: Brain Graph Wachstum
      - neurons: Alle aktiven Neuronen nach Typ gruppiert
      - recent_events: Letzte N verarbeitete Events
      - module_context: Aktueller Modul-Zustand
      - dominant_mood: Aktuelle dominante Stimmung (falls vorhanden)
    """

    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    graph: BrainGraphGrowth = field(default_factory=BrainGraphGrowth)
    context_neurons: List[NeuronSnapshot] = field(default_factory=list)
    state_neurons: List[NeuronSnapshot] = field(default_factory=list)
    mood_neurons: List[NeuronSnapshot] = field(default_factory=list)
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    module_context: Dict[str, str] = field(default_factory=dict)  # module_id → state
    dominant_mood: Optional[str] = None
    mood_confidence: float = 0.0
    pipeline_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "pipeline_version": self.pipeline_version,
            "graph": {
                "total_nodes": self.graph.total_nodes,
                "total_edges": self.graph.total_edges,
                "new_nodes_since_last": self.graph.new_nodes_since_last,
                "new_edges_since_last": self.graph.new_edges_since_last,
                "nodes_by_kind": self.graph.nodes_by_kind,
                "edges_by_type": self.graph.edges_by_type,
                "top_active_nodes": self.graph.top_active_nodes,
                "graph_version": self.graph.graph_version,
            },
            "neurons": {
                "context": [n.to_dict() for n in self.context_neurons],
                "state": [n.to_dict() for n in self.state_neurons],
                "mood": [n.to_dict() for n in self.mood_neurons],
            },
            "recent_events": self.recent_events,
            "module_context": self.module_context,
            "dominant_mood": self.dominant_mood,
            "mood_confidence": round(self.mood_confidence, 3),
        }


# ── Internal State ────────────────────────────────────────────────────────────

# Singleton state for brain read model
_brain_state: Dict[str, Any] = {
    "last_graph_nodes": 0,
    "last_graph_edges": 0,
    "recent_events": [],
    "max_recent_events": 50,
    "_lock": None,
}

# ── Public API ────────────────────────────────────────────────────────────────


def get_brain_summary(
    brain_graph_service: Any = None,
    neuron_manager: Any = None,
    module_registry: Any = None,
    *,
    recent_events_limit: int = 20,
) -> Dict[str, Any]:
    """
    Baue einen vollständigen Brain Summary Snapshot.

    Args:
        brain_graph_service: BrainGraphService Instanz (optional)
        neuron_manager:      NeuronManager Instanz (optional)
        module_registry:     ModuleRegistry Instanz (optional)
        recent_events_limit: Anzahl der recent events im Snapshot

    Returns:
        Dict mit graph, neurons, module_context, recent_events
    """
    snapshot = build_brain_activity_snapshot(
        brain_graph_service=brain_graph_service,
        neuron_manager=neuron_manager,
        module_registry=module_registry,
        recent_events_limit=recent_events_limit,
    )
    return snapshot.to_dict()


def build_brain_activity_snapshot(
    brain_graph_service: Any = None,
    neuron_manager: Any = None,
    module_registry: Any = None,
    *,
    recent_events_limit: int = 20,
) -> BrainActivitySnapshot:
    """
    Baue einen BrainActivitySnapshot aus den aktuellen Services.

    Diese Funktion kann direkt von api/v1/ Endpoints aufgerufen werden.
    """
    now_str = datetime.now(timezone.utc).isoformat()

    # ── Brain Graph ───────────────────────────────────────────────────────
    graph = _build_graph_growth(brain_graph_service)

    # ── Neurons ──────────────────────────────────────────────────────────
    context_neurons, state_neurons, mood_neurons = _build_neuron_snapshots(neuron_manager)

    # ── Recent Events ────────────────────────────────────────────────────
    recent = list(reversed(_brain_state["recent_events"]))[:recent_events_limit]

    # ── Module Context ───────────────────────────────────────────────────
    module_ctx = _build_module_context(module_registry)

    # ── Mood ─────────────────────────────────────────────────────────────
    dominant_mood, mood_confidence = _extract_dominant_mood(neuron_manager)

    return BrainActivitySnapshot(
        generated_at=now_str,
        graph=graph,
        context_neurons=context_neurons,
        state_neurons=state_neurons,
        mood_neurons=mood_neurons,
        recent_events=recent,
        module_context=module_ctx,
        dominant_mood=dominant_mood,
        mood_confidence=mood_confidence,
    )


def feed_brain(event: Dict[str, Any]) -> None:
    """
    Expliziter Feed eines Events in das Brain Read Model.

    Wird von ingest/event_processor.py nach der normalen Event-Verarbeitung
    aufgerufen, um das Read Model mit aktuellen Events zu füllen.

    Das Event sollte ein normalisiertes Event-Dict sein mit keys:
      - entity_id, domain, kind, ts/timestamp, und optional new_state
    """
    entry: Dict[str, Any] = {
        "entity_id": event.get("entity_id", ""),
        "domain": event.get("domain", ""),
        "kind": event.get("kind", ""),
        "ts": event.get("ts") or event.get("timestamp") or int(time.time() * 1000),
        "source": event.get("source", "unknown"),
    }

    state_val = (
        event.get("new_state")
        or (event.get("new", {}).get("state") if isinstance(event.get("new"), dict) else None)
        or ""
    )
    if state_val:
        entry["state"] = str(state_val)

    _brain_state["recent_events"].append(entry)

    # Bound the event list
    max_events = _brain_state["max_recent_events"]
    events = _brain_state["recent_events"]
    if len(events) > max_events:
        _brain_state["recent_events"] = events[-max_events:]


def update_graph_growth_snapshot(
    total_nodes: int,
    total_edges: int,
    nodes_by_kind: Optional[Dict[str, int]] = None,
    edges_by_type: Optional[Dict[str, int]] = None,
    top_active_nodes: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Aktualisiere den Graph-Wachstums-Snapshot im Read Model.

    Wird von BrainGraphService nach Operationen aufgerufen, die neue
    Knoten/Kanten hinzugefügt haben.
    """
    prev_nodes = _brain_state["last_graph_nodes"]
    prev_edges = _brain_state["last_graph_edges"]

    _brain_state["last_graph_nodes"] = total_nodes
    _brain_state["last_graph_edges"] = total_edges

    # Update stored growth metadata (used by _build_graph_growth)
    _brain_state["_graph_nodes"] = total_nodes
    _brain_state["_graph_edges"] = total_edges
    _brain_state["_nodes_by_kind"] = nodes_by_kind or {}
    _brain_state["_edges_by_type"] = edges_by_type or {}
    _brain_state["_top_active_nodes"] = top_active_nodes or []
    _brain_state["_growth_new_nodes"] = max(0, total_nodes - prev_nodes)
    _brain_state["_growth_new_edges"] = max(0, total_edges - prev_edges)
    _brain_state["_graph_version"] = _brain_state.get("_graph_version", 0) + 1


# ── Internal Builders ────────────────────────────────────────────────────────


def _build_graph_growth(brain_graph_service: Any) -> BrainGraphGrowth:
    """Baue Graph-Growth-Snapshot aus BrainGraphService."""
    if brain_graph_service is None:
        return BrainActivitySnapshot().graph

    try:
        stats = brain_graph_service.get_stats()
    except Exception:
        return BrainActivitySnapshot().graph

    total_nodes = stats.get("nodes_count", 0)
    total_edges = stats.get("edges_count", 0)

    # Compute growth since last snapshot
    prev_nodes = _brain_state.get("last_graph_nodes", 0)
    prev_edges = _brain_state.get("last_graph_edges", 0)

    # Update stored snapshot
    _brain_state["last_graph_nodes"] = total_nodes
    _brain_state["last_graph_edges"] = total_edges

    # Aggregate nodes_by_kind from store
    nodes_by_kind: Dict[str, int] = {}
    edges_by_type: Dict[str, int] = {}

    try:
        graph_state = brain_graph_service.get_graph_state(limit_nodes=1000, limit_edges=2000)
        nodes = graph_state.get("nodes", [])
        edges = graph_state.get("edges", [])

        for node in nodes:
            kind = str(node.get("kind", "unknown"))
            nodes_by_kind[kind] = nodes_by_kind.get(kind, 0) + 1

        for edge in edges:
            etype = str(edge.get("type", "unknown"))
            edges_by_type[etype] = edges_by_type.get(etype, 0) + 1

        # Top active nodes by score
        sorted_nodes = sorted(
            [(n.get("id", ""), n.get("score", 0.0)) for n in nodes],
            key=lambda x: x[1], reverse=True,
        )[:10]
        top_active_nodes = [{"id": nid, "score": round(score, 3)} for nid, score in sorted_nodes]

    except Exception:
        nodes_by_kind = _brain_state.get("_nodes_by_kind", {})
        edges_by_type = _brain_state.get("_edges_by_type", {})
        top_active_nodes = _brain_state.get("_top_active_nodes", [])
        total_nodes = _brain_state.get("_graph_nodes", total_nodes)
        total_edges = _brain_state.get("_graph_edges", total_edges)

    return BrainGraphGrowth(
        total_nodes=total_nodes,
        total_edges=total_edges,
        new_nodes_since_last=max(0, total_nodes - prev_nodes),
        new_edges_since_last=max(0, total_edges - prev_edges),
        nodes_by_kind=nodes_by_kind,
        edges_by_type=edges_by_type,
        top_active_nodes=top_active_nodes,
        graph_version=_brain_state.get("_graph_version", 0),
    )


def _build_neuron_snapshots(neuron_manager: Any) -> tuple[List[NeuronSnapshot], List[NeuronSnapshot], List[NeuronSnapshot]]:
    """Baue Neuron-Snapshots aus NeuronManager."""
    context: List[NeuronSnapshot] = []
    state: List[NeuronSnapshot] = []
    mood: List[NeuronSnapshot] = []

    if neuron_manager is None:
        return context, state, mood

    try:
        all_neurons = neuron_manager.get_all_neurons()
    except Exception:
        return context, state, mood

    for nid, neuron in all_neurons.items():
        try:
            ntype = nid.split(".", 1)[0] if "." in nid else "unknown"
            s = neuron.state if hasattr(neuron, "state") else None
            if s is None:
                continue

            snap = NeuronSnapshot(
                name=nid,
                neuron_type=ntype,
                value=float(getattr(s, "value", 0.0)),
                active=bool(getattr(s, "active", False)),
                confidence=float(getattr(s, "confidence", 0.0)),
                last_update=str(getattr(s, "last_update", "") or ""),
                last_trigger=str(getattr(s, "last_trigger", "") or ""),
                trigger_count=int(getattr(s, "trigger_count", 0)),
            )

            if ntype == "context":
                context.append(snap)
            elif ntype == "state":
                state.append(snap)
            elif ntype == "mood":
                mood.append(snap)
        except Exception:
            continue

    return context, state, mood


def _build_module_context(module_registry: Any) -> Dict[str, str]:
    """Baue Module-Context aus ModuleRegistry."""
    if module_registry is None:
        return {}

    try:
        all_states = module_registry.get_all_states()
        if not all_states:
            # Return default states for known modules
            defaults = {
                "licht": "active",
                "bewegung": "active",
                "heiz": "active",
                "musik": "active",
                "medien": "active",
                "kamera": "active",
                "praesenz": "active",
                "helligkeit": "active",
                "energie": "active",
                "mood_engine": "active",
            }
            return defaults
        return all_states
    except Exception:
        return {}


def _extract_dominant_mood(neuron_manager: Any) -> tuple[Optional[str], float]:
    """Extrahiere dominante Stimmung aus NeuronManager."""
    if neuron_manager is None:
        return None, 0.0

    try:
        summary = neuron_manager.get_mood_summary()
        return summary.get("mood"), summary.get("confidence", 0.0)
    except Exception:
        pass

    return None, 0.0


def get_brain_activity_for_api(
    brain_graph_service: Any = None,
    neuron_manager: Any = None,
    module_registry: Any = None,
) -> Dict[str, Any]:
    """
    Alias für get_brain_summary() — API-freundliches Interface.

    Exponiert von api/v1/ als Read Model Endpoint.
    """
    return get_brain_summary(
        brain_graph_service=brain_graph_service,
        neuron_manager=neuron_manager,
        module_registry=module_registry,
    )


__all__ = [
    "BrainActivitySnapshot",
    "BrainGraphGrowth",
    "NeuronSnapshot",
    "build_brain_activity_snapshot",
    "feed_brain",
    "get_brain_summary",
    "get_brain_activity_for_api",
    "update_graph_growth_snapshot",
]
