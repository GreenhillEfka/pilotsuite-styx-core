from hashlib import sha256

from flask import Blueprint, current_app, jsonify, request

from copilot_core.brain_graph.provider import get_graph_service
from copilot_core.storage.candidates import CandidateStore, rank_score, generate_explanation
from copilot_core.api.api_errors import unauthorized, bad_request
from copilot_core.api.pagination import cursor_page

bp = Blueprint("candidates", __name__, url_prefix="/api/v1/candidates")

from copilot_core.api.security import validate_token as _validate_token

import logging

_LOGGER = logging.getLogger(__name__)


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return unauthorized("Valid X-Auth-Token or Bearer token required")


_STORE: CandidateStore | None = None


def _store() -> CandidateStore:
    global _STORE
    if _STORE is not None:
        return _STORE

    cfg = current_app.config.get("COPILOT_CFG")
    _STORE = CandidateStore(
        max_items=int(getattr(cfg, "candidates_max", 500)),
        persist=bool(getattr(cfg, "candidates_persist", False)),
        json_path=str(getattr(cfg, "candidates_json_path", "/data/candidates.json")),
    )
    return _STORE


@bp.post("")
def upsert_candidate():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return bad_request("Expected JSON object", req=request)

    cand = _store().upsert(payload)
    return jsonify({"ok": True, "candidate": cand})


@bp.get("")
def list_candidates():
    """List candidates with cursor-based pagination.

    Query params:
    - limit: Page size 1-100 (default 50)
    - after: Opaque cursor — items after this rank_score+id
    - before: Opaque cursor — items before this rank_score+id
    - kind: Filter by candidate kind (optional)
    - ranked: Sort by rank_score descending (default true)

    Response includes:
    - items: Current page of candidates
    - count: Number of items in this response
    - page_info: has_next_page, has_previous_page, next_cursor, previous_cursor
    - pagination: limit, direction
    """
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 100))

    kind = request.args.get("kind")
    ranked = request.args.get("ranked", "true").lower() in ("true", "1", "yes")
    after = request.args.get("after")
    before = request.args.get("before")

    # Fetch limit+1 to detect has_next/has_prev
    fetch_limit = limit + 1

    if ranked:
        all_items = _store().list_ranked(limit=fetch_limit, kind=kind, with_explanation=True)
    else:
        all_items = _store().list(limit=fetch_limit, kind=kind)

    # Apply cursor filters
    if after:
        from copilot_core.api.pagination import _decode_cursor
        cur = _decode_cursor(after)
        if cur and "id" in cur:
            after_id = cur["id"]
            all_items = [i for i in all_items if i.get("id") != after_id]
    if before:
        from copilot_core.api.pagination import _decode_cursor
        cur = _decode_cursor(before)
        if cur and "id" in cur:
            before_id = cur["id"]
            all_items = [i for i in all_items if i.get("id") != before_id]

    # Determine has_next / has_prev
    has_next = len(all_items) > limit
    has_prev = bool(after or before)
    items = all_items[:limit]

    page = cursor_page(
        items=items,
        before=before,
        after=after,
        has_next=has_next,
        has_prev=has_prev,
        limit=limit,
        total=None,  # CandidateStore is unbounded in this implementation
        build_next=lambda item: item.get("rank_score"),
        build_prev=lambda item: item.get("rank_score"),
        item_to_dict=True,
    )
    return jsonify(page)


@bp.get("/<candidate_id>")
def get_candidate(candidate_id: str):
    it = _store().get(candidate_id)
    if not it:
        return bad_request(f"Candidate '{candidate_id}' not found", req=request)
    # Enrich with score and explanation
    enriched = dict(it)
    try:
        enriched["rank_score"] = rank_score(enriched)
        enriched["explanation"] = generate_explanation(enriched)
    except Exception:
        pass
    return jsonify({"ok": True, "candidate": enriched})


@bp.delete("/<candidate_id>")
def delete_candidate(candidate_id: str):
    ok = _store().delete(candidate_id)
    return jsonify({"ok": ok})


@bp.post("/<candidate_id>/feedback")
def candidate_feedback(candidate_id: str):
    """Record accept/reject/snooze feedback for a candidate.

    Body: {"action": "accepted"|"rejected"|"snoozed"}

    If the candidate has ``data.from`` and ``data.to`` fields (habitus rule
    candidates), the feedback is forwarded to the HabitusFeedbackStore so
    future mining runs reinforce or suppress the pattern.
    """
    payload = request.get_json(silent=True) or {}
    action = payload.get("action", "")
    if action not in ("accepted", "rejected", "snoozed"):
        return jsonify({"ok": False, "error": "action must be accepted, rejected, or snoozed"}), 400

    candidate = _store().get(candidate_id)
    if not candidate:
        return jsonify({"ok": False, "error": "not_found"}), 404

    # Update candidate status in store
    candidate["attributes"] = candidate.get("attributes") or {}
    candidate["attributes"]["feedback_action"] = action
    _store().upsert(candidate)

    # Forward to habitus feedback store if this is a rule-based candidate
    _forward_habitus_feedback(candidate, action)

    return jsonify({"ok": True, "action": action, "candidate_id": candidate_id})


def _forward_habitus_feedback(candidate: dict, action: str) -> None:
    """Forward candidate feedback to the habitus miner feedback store."""
    try:
        attrs = candidate.get("attributes") or {}
        data = attrs if isinstance(attrs, dict) else {}

        # Try to derive pattern key from candidate data
        # Candidates from graph_candidates have data.from / data.to
        from_id = data.get("from", "")
        to_id = data.get("to", "")

        # Also check nested 'data' key (graph_edge_candidate format)
        if not from_id and isinstance(candidate.get("attributes"), dict):
            nested = candidate["attributes"]
            from_id = nested.get("from", "")
            to_id = nested.get("to", "")

        if not from_id or not to_id:
            # Not a rule-based candidate — skip silently
            return

        pattern_key = f"{from_id}->{to_id}"

        # Lazy-import to avoid circular dependency
        from copilot_core.habitus_miner.feedback_store import HabitusFeedbackStore
        from pathlib import Path

        cfg = current_app.config.get("COPILOT_CFG")
        if not cfg:
            return

        storage_dir = Path(cfg.data_dir) / "habitus_miner"
        store = HabitusFeedbackStore(storage_dir)
        store.record_feedback(pattern_key, action)
        _LOGGER.info("Forwarded candidate feedback to habitus: %s -> %s", pattern_key, action)
    except Exception:
        _LOGGER.debug("Failed to forward candidate feedback to habitus", exc_info=True)


@bp.get("/stats")
def candidates_stats():
    """Candidate store statistics for health checks."""
    items = _store().list(limit=0)
    return jsonify({
        "ok": True,
        "count": len(items),
        "max_items": _store()._max_items
    })


@bp.get("/graph_candidates")
def graph_candidates():
    """Generate governance-ready candidates from the Brain Graph.

    v0.1 kernel: deterministic, bounded, privacy-first. No raw events.

    This endpoint only PREVIEWS candidates. Home Assistant decides whether to
    offer them as Repairs issues.
    """

    try:
        limit = int(request.args.get("limit", "10"))
    except Exception:
        limit = 10
    limit = max(1, min(limit, 25))

    # Filter edge types (v0.1: conservative).
    allow_types = set(request.args.getlist("type") or ["controls", "observed_with"])  # default

    # Pull a bounded graph view.
    state = get_graph_service().export_state(limit_nodes=300, limit_edges=600)
    edges = state.get("edges") if isinstance(state, dict) else None
    if not isinstance(edges, list):
        edges = []

    # Take top edges by weight.
    edges = [e for e in edges if isinstance(e, dict) and e.get("type") in allow_types]
    edges.sort(key=lambda e: float(e.get("weight") or 0.0), reverse=True)

    items: list[dict] = []
    for e in edges:
        if len(items) >= limit:
            break

        from_id = str(e.get("from") or "")
        to_id = str(e.get("to") or "")
        typ = str(e.get("type") or "")
        w = float(e.get("weight") or 0.0)
        updated = int(e.get("updated_at_ms") or 0)

        if not from_id or not to_id or not typ:
            continue
        if w <= 0:
            continue

        raw = f"{from_id}|{typ}|{to_id}".encode("utf-8")
        hid = sha256(raw).hexdigest()[:12]
        candidate_id = f"graph_edge_{typ}_{hid}".replace("-", "_")

        # Best-effort extraction of HA entities for display.
        ents: list[str] = []
        for nid in (from_id, to_id):
            if nid.startswith("ha.entity:"):
                ents.append(nid.split(":", 1)[1])
        ents = list(dict.fromkeys(ents))

        title = f"Graph: Edge vorschlagen ({typ})"
        summary = f"Beziehung im Brain Graph: {from_id} —[{typ}]→ {to_id} (weight≈{w:.2f})."

        items.append(
            {
                "candidate_id": candidate_id,
                "kind": "seed",
                "title": title,
                "seed_source": "brain_graph",
                "seed_entities": ents,
                "seed_text": summary,
                "data": {
                    "candidate_type": "graph_edge_candidate",
                    "from": from_id,
                    "to": to_id,
                    "edge_type": typ,
                    "evidence": {
                        "weight": round(w, 6),
                        "updated_at_ms": updated,
                        "graph_generated_at_ms": int(state.get("generated_at_ms") or 0),
                    },
                },
            }
        )

    # Enrich with ranking scores and explanations, then sort
    for item in items:
        try:
            # Map graph data into attributes format for rank_score compatibility
            data = item.get("data") or {}
            item["attributes"] = data
            item["rank_score"] = rank_score(item, all_candidates=items)
            item["explanation"] = generate_explanation(item)
        except Exception:
            item["rank_score"] = 0.0
            item["explanation"] = ""
    items.sort(key=lambda c: c.get("rank_score", 0.0), reverse=True)

    return jsonify({"ok": True, "count": len(items), "items": items, "types": sorted(list(allow_types))})
