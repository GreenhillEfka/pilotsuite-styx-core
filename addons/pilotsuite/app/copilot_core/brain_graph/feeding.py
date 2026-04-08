from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable

from copilot_core.brain_graph.service import BrainGraphService


def _as_list(x: Any) -> list[Any]:
    if isinstance(x, list):
        return x
    return []


def _entity_node_id(entity_id: str) -> str:
    return f"ha.entity:{entity_id}"


def _zone_node_id(zone_id: str) -> str:
    return f"zone:{zone_id}"


def _intent_node_id(domain: str, service: str) -> str:
    return f"ha.intent:{domain}.{service}"


def feed_events_to_graph(
    svc: BrainGraphService,
    events: Iterable[dict[str, Any]],
    *,
    observed_with_max_pairs: int = 64,
) -> dict[str, int]:
    """Update the Brain Graph from ingested events (privacy-first).

    Expected event envelope (as forwarded by HA component):
      {type, entity_id, attributes:{zone_ids, domain, service, entity_ids}}

    This function intentionally does *not* persist raw state attributes.
    """

    touched_nodes = 0
    touched_edges = 0

    # Track entities that appear in this ingest batch for optional co-occurrence edges.
    batch_entities: list[str] = []

    for evt in events:
        if not isinstance(evt, dict):
            continue

        typ = str(evt.get("type") or "")
        entity_id = str(evt.get("entity_id") or "").strip()
        attrs = evt.get("attributes") if isinstance(evt.get("attributes"), dict) else {}

        if typ == "state_changed":
            if not entity_id:
                continue

            # touch entity
            svc.touch_node(_entity_node_id(entity_id), kind="entity", label=entity_id)
            touched_nodes += 1
            batch_entities.append(entity_id)

            # zones
            for zid in _as_list(attrs.get("zone_ids")):
                zone_id = str(zid).strip()
                if not zone_id:
                    continue
                svc.touch_node(_zone_node_id(zone_id), kind="zone", label=zone_id)
                svc.touch_edge(_entity_node_id(entity_id), "in_zone", _zone_node_id(zone_id))
                touched_nodes += 1
                touched_edges += 1

        elif typ == "call_service":
            domain = str(attrs.get("domain") or "").strip()
            service = str(attrs.get("service") or "").strip()
            if not domain or not service:
                continue

            intent_id = _intent_node_id(domain, service)
            svc.touch_node(intent_id, kind="module", label=f"{domain}.{service}")
            touched_nodes += 1

            # Link to entities (from allowlisted sanitized list)
            ent_ids = []
            for eid in _as_list(attrs.get("entity_ids")):
                se = str(eid).strip()
                if se:
                    ent_ids.append(se)

            # Back-compat: if only entity_id is present.
            if entity_id and entity_id not in ent_ids:
                ent_ids.append(entity_id)

            for eid in ent_ids:
                svc.touch_node(_entity_node_id(eid), kind="entity", label=eid)
                svc.touch_edge(intent_id, "controls", _entity_node_id(eid))
                touched_nodes += 1
                touched_edges += 1
                batch_entities.append(eid)

            # Link to zones if present
            for zid in _as_list(attrs.get("zone_ids")):
                zone_id = str(zid).strip()
                if not zone_id:
                    continue
                svc.touch_node(_zone_node_id(zone_id), kind="zone", label=zone_id)
                svc.touch_edge(intent_id, "controls", _zone_node_id(zone_id))
                touched_nodes += 1
                touched_edges += 1

        else:
            # ignore unknown types
            continue

    # Optional: add co-occurrence links (bounded)
    # Use unique entity IDs, deterministic ordering.
    uniq_entities = sorted({e for e in batch_entities if e})
    pairs_added = 0
    if len(uniq_entities) >= 2 and observed_with_max_pairs > 0:
        for a, b in combinations(uniq_entities, 2):
            # bound the explosion
            if pairs_added >= observed_with_max_pairs:
                break
            # store as a single directed edge for dedupe stability
            svc.touch_edge(_entity_node_id(a), "observed_with", _entity_node_id(b))
            touched_edges += 1
            pairs_added += 1

    # Keep the store bounded.
    svc.prune()

    return {
        "nodes_touched": touched_nodes,
        "edges_touched": touched_edges,
        "observed_with_pairs": pairs_added,
    }
