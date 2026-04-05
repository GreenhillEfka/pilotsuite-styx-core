

# ── SLICE 157: Cache API Expansion ─────────────────────────────────

@bp.get("/keys")
def cache_keys():
    """List cached keys.
    
    Query params:
    - pattern: Key pattern filter (optional, supports * wildcard)
    - limit: Max keys (default 100)
    """
    from copilot_core.cache.manager import get_cache_manager
    
    pattern = request.args.get("pattern")
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    limit = max(1, min(limit, 1000))
    
    try:
        manager = get_cache_manager()
        keys = manager.list_keys(pattern=pattern, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to list cache keys: %s", e)
        keys = []
    
    return jsonify({
        "ok": True,
        "keys": keys,
        "count": len(keys),
        "pattern": pattern,
        "limit": limit
    })


@bp.get("/keys/<key>")
def cache_get_key(key):
    """Get cached value for a specific key.
    
    Returns the cached value and metadata (TTL, size, etc.).
    """
    from copilot_core.cache.manager import get_cache_manager
    
    try:
        manager = get_cache_manager()
        value = manager.get(key=key)
        metadata = manager.get_key_metadata(key=key)
    except Exception as e:
        _LOGGER.warning("Failed to get cache key: %s", e)
        value = None
        metadata = {}
    
    if value is None:
        return jsonify({
            "ok": False,
            "error": "Key not found"
        }), 404
    
    return jsonify({
        "ok": True,
        "key": key,
        "value": value,
        "metadata": metadata
    })


@bp.delete("/keys/<key>")
def cache_invalidate_key(key):
    """Invalidate a specific cache key.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("INVALIDATE_CACHE_KEY", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.cache.manager import get_cache_manager
    
    try:
        manager = get_cache_manager()
        success = manager.invalidate(key=key)
    except Exception as e:
        _LOGGER.warning("Failed to invalidate cache key: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "key": key
    })


@bp.delete("/keys/pattern")
def cache_invalidate_pattern():
    """Invalidate cache keys matching a pattern.
    
    Requires admin token.
    
    Query params:
    - pattern: Key pattern (supports * wildcard)
    """
    auth_error = _require_admin_mutation("INVALIDATE_CACHE_PATTERN", "Admin token required")
    if auth_error:
        return auth_error
    
    pattern = request.args.get("pattern")
    
    if not pattern:
        return jsonify({
            "ok": False,
            "error": "Missing pattern parameter"
        }), 400
    
    from copilot_core.cache.manager import get_cache_manager
    
    try:
        manager = get_cache_manager()
        result = manager.invalidate_pattern(pattern=pattern)
        success = result.get("success", False)
        invalidated = result.get("invalidated_count", 0)
    except Exception as e:
        _LOGGER.warning("Failed to invalidate cache pattern: %s", e)
        success = False
        invalidated = 0
    
    return jsonify({
        "ok": success,
        "pattern": pattern,
        "invalidated": invalidated
    })


@bp.get("/analytics")
def cache_analytics():
    """Get cache analytics.
    
    Query params:
    - hours: Time range (default 24)
    """
    from copilot_core.cache.manager import get_cache_manager
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    hours = max(1, min(hours, 720))
    
    try:
        manager = get_cache_manager()
        analytics = manager.get_analytics(hours=hours)
    except Exception as e:
        _LOGGER.warning("Failed to get cache analytics: %s", e)
        analytics = {
            "total_hits": 0,
            "total_misses": 0,
            "hit_rate": 0.0,
            "evictions": 0,
            "avg_ttl_seconds": 0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "hours": hours,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
