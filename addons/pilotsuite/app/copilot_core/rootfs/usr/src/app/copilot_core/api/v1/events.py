from flask import Blueprint, current_app, jsonify, request

from copilot_core.brain_graph.feeding import feed_events_to_graph
from copilot_core.brain_graph.provider import get_graph_service
from copilot_core.storage.events import EventStore

bp = Blueprint("events", __name__, url_prefix="/events")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


# Lazy singleton per-process
_STORE: EventStore | None = None


def _store() -> EventStore:
    global _STORE
    if _STORE is not None:
        return _STORE

    cfg = current_app.config.get("COPILOT_CFG")
    _STORE = EventStore(
        cache_max=int(getattr(cfg, "events_cache_max", 500)),
        persist=bool(getattr(cfg, "events_persist", False)),
        jsonl_path=str(getattr(cfg, "events_jsonl_path", "/data/events.jsonl")),
        idempotency_ttl_seconds=int(getattr(cfg, "events_idempotency_ttl_seconds", 20 * 60)),
        idempotency_lru_max=int(getattr(cfg, "events_idempotency_lru_max", 10_000)),
    )
    return _STORE


@bp.post("")
def ingest_event():
    payload = request.get_json(silent=True) or {}

    # Accept either a single event or a batch: {items:[...]}
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = [x for x in payload["items"] if isinstance(x, dict)]
        n, stored_events = _store().extend(items)

        # Graph feeding happens *after* dedupe: only use stored events.
        graph_stats = feed_events_to_graph(get_graph_service(), stored_events)
        return jsonify({"ok": True, "ingested": n, "graph": graph_stats})

    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "expected JSON object"}), 400

    idem = (
        request.headers.get("Idempotency-Key")
        or request.headers.get("X-Idempotency-Key")
        or request.headers.get("X-Event-Id")
        or ""
    )

    evt, stored = _store().append(payload, idempotency_key=str(idem))
    if stored:
        graph_stats = feed_events_to_graph(get_graph_service(), [evt])
    else:
        graph_stats = {"nodes_touched": 0, "edges_touched": 0, "observed_with_pairs": 0}

    return jsonify(
        {
            "ok": True,
            "stored": stored,
            "deduped": (not stored),
            "event": evt,
            "graph": graph_stats,
        }
    )


@bp.get("")
def list_events():
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50

    since = request.args.get("since")
    items = _store().list(limit=limit, since_ts=since)
    return jsonify({"ok": True, "count": len(items), "items": items})
