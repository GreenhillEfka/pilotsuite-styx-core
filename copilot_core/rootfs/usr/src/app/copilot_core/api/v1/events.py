

# ── SLICE 145: Events API Expansion ─────────────────────────────────

@bp.get("/filtered")
def events_filtered():
    """Get events with advanced filtering.
    
    Query params:
    - type: Event type filter (optional)
    - source: Event source filter (optional)
    - zone_id: Zone filter (optional)
    - hours: Time range (default 24)
    - limit: Max events (default 100)
    """
    from copilot_core.events.store import get_events_store
    
    event_type = request.args.get("type")
    source = request.args.get("source")
    zone_id = request.args.get("zone_id")
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    hours = max(1, min(hours, 720))
    limit = max(1, min(limit, 1000))
    
    try:
        store = get_events_store()
        events = store.get_filtered_events(
            event_type=event_type,
            source=source,
            zone_id=zone_id,
            hours=hours,
            limit=limit
        )
    except Exception as e:
        _LOGGER.warning("Failed to get filtered events: %s", e)
        events = []
    
    return jsonify({
        "ok": True,
        "events": events,
        "count": len(events),
        "filters": {
            "type": event_type,
            "source": source,
            "zone_id": zone_id,
            "hours": hours,
            "limit": limit
        }
    })


@bp.get("/aggregation")
def events_aggregation():
    """Get aggregated events by type/source.
    
    Query params:
    - hours: Time range (default 24)
    - group_by: Group by type|source|zone (default: type)
    """
    from copilot_core.events.store import get_events_store
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    group_by = request.args.get("group_by", "type")
    
    hours = max(1, min(hours, 720))
    
    try:
        store = get_events_store()
        aggregation = store.get_aggregation(hours=hours, group_by=group_by)
    except Exception as e:
        _LOGGER.warning("Failed to get event aggregation: %s", e)
        aggregation = []
    
    return jsonify({
        "ok": True,
        "aggregation": aggregation,
        "hours": hours,
        "group_by": group_by,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/replay")
def events_replay():
    """Replay events for debugging/testing.
    
    Requires admin token.
    
    Body:
    - event_ids: List of event IDs to replay
    - target: Replay target (default: same)
    """
    auth_error = _require_admin_mutation("REPLAY_EVENTS", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    event_ids = data.get("event_ids", [])
    target = data.get("target", "same")
    
    if not event_ids:
        return jsonify({
            "ok": False,
            "error": "Missing event_ids"
        }), 400
    
    from copilot_core.events.store import get_events_store
    
    try:
        store = get_events_store()
        result = store.replay_events(event_ids=event_ids, target=target)
        success = True
        replayed = result.get("replayed", len(event_ids))
    except Exception as e:
        _LOGGER.warning("Failed to replay events: %s", e)
        success = False
        replayed = 0
    
    return jsonify({
        "ok": success,
        "replayed": replayed,
        "total": len(event_ids),
        "target": target
    })
