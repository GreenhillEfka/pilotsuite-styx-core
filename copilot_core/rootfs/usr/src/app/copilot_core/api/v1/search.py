"""Quick Search API for PilotSuite.

Provides fast search across:
- HA Entities (by name, domain, state, area)
- Automations (by name, trigger, condition)
- Scripts (by name, action)
- Scenes (by name, entity)
- Services (by domain, service)

Endpoints:
- GET /api/v1/search?q=<query> - Full-text search
- GET /api/v1/search/entities?domain=<domain>&state=<state> - Entity filters
- GET /api/v1/search/automations?trigger=<trigger> - Automation search
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest

_LOGGER = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("search", __name__, url_prefix="/search")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401

# Search result types
RESULT_TYPE_ENTITY = "entity"
RESULT_TYPE_AUTOMATION = "automation"
RESULT_TYPE_SCRIPT = "script"
RESULT_TYPE_SCENE = "scene"
RESULT_TYPE_SERVICE = "service"
VALID_RESULT_TYPES = {
    RESULT_TYPE_ENTITY,
    RESULT_TYPE_AUTOMATION,
    RESULT_TYPE_SCRIPT,
    RESULT_TYPE_SCENE,
    RESULT_TYPE_SERVICE,
}


@dataclass
class SearchResult:
    """Single search result."""
    id: str
    type: str
    title: str
    subtitle: str = ""
    domain: str = ""
    state: str = ""
    icon: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Search response with results."""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    total_count: int = 0
    execution_time_ms: float = 0.0


class QuickSearchEngine:
    """Fast search engine for HA entities and automations."""
    
    # Domain to icon mapping
    DOMAIN_ICONS = {
        "light": "mdi:lightbulb",
        "switch": "mdi:toggle-switch",
        "sensor": "mdi:eye",
        "binary_sensor": "mdi:motion-sensor",
        "climate": "mdi:thermostat",
        "media_player": "mdi:play-circle",
        "cover": "mdi:blinds",
        "lock": "mdi:lock",
        "camera": "mdi:cctv",
        "fan": "mdi:fan",
        "vacuum": "mdi:robot-vacuum",
        "alarm_control_panel": "mdi:shield-lock",
        "person": "mdi:account",
        "device_tracker": "mdi:crosshairs-gps",
        "zone": "mdi:map-marker",
        "group": "mdi:group",
        "scene": "mdi:palette",
        "script": "mdi:script-text",
        "automation": "mdi:robot",
        "input_boolean": "mdi:toggle-switch",
        "input_number": "mdi:numeric",
        "input_text": "mdi:textbox",
        "input_select": "mdi:form-dropdown",
    }
    
    def __init__(self):
        self._entities: Dict[str, Dict[str, Any]] = {}
        self._automations: Dict[str, Dict[str, Any]] = {}
        self._scripts: Dict[str, Dict[str, Any]] = {}
        self._scenes: Dict[str, Dict[str, Any]] = {}
        self._services: Dict[str, Dict[str, Any]] = {}
    
    def update_entities(self, states: Dict[str, Dict[str, Any]]) -> None:
        """Update entity index."""
        self._entities = states
    
    def update_automations(self, automations: Dict[str, Dict[str, Any]]) -> None:
        """Update automation index."""
        self._automations = automations
    
    def update_scripts(self, scripts: Dict[str, Dict[str, Any]]) -> None:
        """Update script index."""
        self._scripts = scripts
    
    def update_scenes(self, scenes: Dict[str, Dict[str, Any]]) -> None:
        """Update scene index."""
        self._scenes = scenes
    
    def update_services(self, services: Dict[str, Dict[str, Any]]) -> None:
        """Update services index."""
        self._services = services
    
    def search(
        self,
        query: str,
        types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> SearchResponse:
        """Perform search across all indexed items."""
        import time
        start = time.time()
        
        query_lower = query.lower().strip()
        if not query_lower:
            return SearchResponse(query=query, results=[], total_count=0)
        
        # Default to all types
        if not types:
            types = [RESULT_TYPE_ENTITY, RESULT_TYPE_AUTOMATION, RESULT_TYPE_SCRIPT, RESULT_TYPE_SCENE, RESULT_TYPE_SERVICE]
        
        results: List[SearchResult] = []
        
        # Search each type
        if RESULT_TYPE_ENTITY in types:
            results.extend(self._search_entities(query_lower, limit))
        
        if RESULT_TYPE_AUTOMATION in types:
            results.extend(self._search_automations(query_lower, limit))
        
        if RESULT_TYPE_SCRIPT in types:
            results.extend(self._search_scripts(query_lower, limit))
        
        if RESULT_TYPE_SCENE in types:
            results.extend(self._search_scenes(query_lower, limit))
        
        if RESULT_TYPE_SERVICE in types:
            results.extend(self._search_services(query_lower, limit))
        
        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]
        
        execution_time = (time.time() - start) * 1000
        
        return SearchResponse(
            query=query,
            results=results,
            total_count=len(results),
            execution_time_ms=execution_time,
        )
    
    def _search_entities(self, query: str, limit: int) -> List[SearchResult]:
        """Search entities."""
        results = []
        
        for entity_id, state in self._entities.items():
            score = self._calculate_score(query, entity_id, state)
            if score > 0:
                domain = entity_id.split(".")[0]
                friendly_name = state.get("attributes", {}).get("friendly_name", entity_id)
                current_state = state.get("state", "unknown")
                area = state.get("attributes", {}).get("area_id", "")
                
                results.append(SearchResult(
                    id=entity_id,
                    type=RESULT_TYPE_ENTITY,
                    title=friendly_name,
                    subtitle=f"{domain} • {current_state}" + (f" • {area}" if area else ""),
                    domain=domain,
                    state=current_state,
                    icon=self.DOMAIN_ICONS.get(domain, "mdi:circle"),
                    score=score,
                    metadata={
                        "entity_id": entity_id,
                        "area": area,
                        "attributes": self._sanitize_attributes(state.get("attributes", {})),
                    }
                ))
        
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def _search_automations(self, query: str, limit: int) -> List[SearchResult]:
        """Search automations."""
        results = []
        
        for auto_id, config in self._automations.items():
            score = self._calculate_score(query, auto_id, config)
            if score > 0:
                friendly_name = config.get("alias", auto_id)
                last_triggered = config.get("last_triggered")
                enabled = config.get("enabled", True)
                
                # Get trigger info
                triggers = config.get("trigger", [])
                trigger_text = ", ".join([str(t.get("platform", "unknown")) for t in triggers[:2]])
                
                results.append(SearchResult(
                    id=auto_id,
                    type=RESULT_TYPE_AUTOMATION,
                    title=friendly_name,
                    subtitle=f"Trigger: {trigger_text}" + (" • Disabled" if not enabled else ""),
                    domain="automation",
                    state="on" if enabled else "off",
                    icon="mdi:robot",
                    score=score,
                    metadata={
                        "trigger": triggers,
                        "condition": config.get("condition", []),
                        "action": config.get("action", []),
                        "last_triggered": last_triggered,
                        "enabled": enabled,
                    }
                ))
        
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def _search_scripts(self, query: str, limit: int) -> List[SearchResult]:
        """Search scripts."""
        results = []
        
        for script_id, config in self._scripts.items():
            score = self._calculate_score(query, script_id, config)
            if score > 0:
                friendly_name = config.get("alias", script_id)
                
                # Get sequence info
                sequence = config.get("sequence", [])
                action_count = len(sequence)
                
                results.append(SearchResult(
                    id=script_id,
                    type=RESULT_TYPE_SCRIPT,
                    title=friendly_name,
                    subtitle=f"Aktionen: {action_count}",
                    domain="script",
                    state="ready",
                    icon="mdi:script-text",
                    score=score,
                    metadata={
                        "sequence": sequence,
                        "mode": config.get("mode", "single"),
                    }
                ))
        
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def _search_scenes(self, query: str, limit: int) -> List[SearchResult]:
        """Search scenes."""
        results = []
        
        for scene_id, config in self._scenes.items():
            score = self._calculate_score(query, scene_id, config)
            if score > 0:
                friendly_name = config.get("alias", scene_id)
                
                # Get affected entities
                entities = config.get("entities", {})
                entity_count = len(entities)
                
                results.append(SearchResult(
                    id=scene_id,
                    type=RESULT_TYPE_SCENE,
                    title=friendly_name,
                    subtitle=f"Entitäten: {entity_count}",
                    domain="scene",
                    state="scening",
                    icon="mdi:palette",
                    score=score,
                    metadata={
                        "entities": entities,
                    }
                ))
        
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def _search_services(self, query: str, limit: int) -> List[SearchResult]:
        """Search services."""
        results = []
        
        for service_id, config in self._services.items():
            score = self._calculate_score(query, service_id, config)
            if score > 0:
                domain, service = service_id.split(".", 1) if "." in service_id else ("", service_id)
                
                results.append(SearchResult(
                    id=service_id,
                    type=RESULT_TYPE_SERVICE,
                    title=f"{domain}.{service}" if domain else service,
                    subtitle=config.get("description", ""),
                    domain=domain,
                    icon=self.DOMAIN_ICONS.get(domain, "mdi:cog"),
                    score=score,
                    metadata={
                        "fields": config.get("fields", {}),
                    }
                ))
        
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def _calculate_score(self, query: str, item_id: str, config: Dict[str, Any]) -> float:
        """Calculate search relevance score."""
        score = 0.0
        item_id_lower = item_id.lower()
        
        # Exact match (highest score)
        if query == item_id_lower:
            return 1.0
        
        # Starts with query
        if item_id_lower.startswith(query):
            score = 0.9
        # Contains query
        elif query in item_id_lower:
            score = 0.7
        
        # Check friendly name
        friendly_name = config.get("attributes", {}).get("friendly_name", "") or config.get("alias", "")
        if friendly_name:
            friendly_lower = friendly_name.lower()
            if query == friendly_lower:
                score = max(score, 0.95)
            elif friendly_lower.startswith(query):
                score = max(score, 0.85)
            elif query in friendly_lower:
                score = max(score, 0.6)
        
        # Check description (for services)
        description = config.get("description", "")
        if description and query in description.lower():
            score = max(score, 0.4)
        
        # Word boundary bonus
        if score > 0:
            pattern = r'\b' + re.escape(query) + r'\b'
            if re.search(pattern, item_id_lower) or (friendly_name and re.search(pattern, friendly_name.lower())):
                score += 0.1
        
        return min(score, 1.0)
    
    def _sanitize_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive attributes."""
        sensitive_keys = {"access_token", "entity_picture", "icon", "friendly_name"}
        return {k: v for k, v in attributes.items() if k not in sensitive_keys}
    
    def filter_entities(
        self,
        domain: Optional[str] = None,
        state: Optional[str] = None,
        area: Optional[str] = None,
        limit: int = 50,
    ) -> List[SearchResult]:
        """Filter entities by criteria."""
        results = []
        
        for entity_id, entity_state in self._entities.items():
            entity_domain = entity_id.split(".")[0]
            current_state = entity_state.get("state", "")
            attributes = entity_state.get("attributes", {})
            
            # Apply filters
            if domain and entity_domain != domain:
                continue
            if state and current_state != state:
                continue
            if area and attributes.get("area_id") != area:
                continue
            
            friendly_name = attributes.get("friendly_name", entity_id)
            
            results.append(SearchResult(
                id=entity_id,
                type=RESULT_TYPE_ENTITY,
                title=friendly_name,
                subtitle=f"{entity_domain} • {current_state}",
                domain=entity_domain,
                state=current_state,
                icon=self.DOMAIN_ICONS.get(entity_domain, "mdi:circle"),
                score=1.0,
                metadata={"attributes": self._sanitize_attributes(attributes)},
            ))
        
        return results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search index statistics."""
        domains: Dict[str, int] = {}
        for entity_id in self._entities.keys():
            domain = entity_id.split(".")[0]
            domains[domain] = domains.get(domain, 0) + 1
        
        return {
            "entities": len(self._entities),
            "automations": len(self._automations),
            "scripts": len(self._scripts),
            "scenes": len(self._scenes),
            "services": len(self._services),
            "domains": domains,
        }


# Singleton instance
_search_engine: Optional[QuickSearchEngine] = None


def get_search_engine() -> QuickSearchEngine:
    """Get the singleton search engine."""
    global _search_engine
    if _search_engine is None:
        _search_engine = QuickSearchEngine()
    return _search_engine


def _error_response(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _parse_limit(raw_value: str, *, default: int, max_value: int) -> int:
    if raw_value == "":
        return default
    try:
        limit = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"limit must be a positive integer <= {max_value}") from exc
    if limit <= 0 or limit > max_value:
        raise ValueError(f"limit must be a positive integer <= {max_value}")
    return limit


def _parse_types(raw_value: str) -> Optional[List[str]]:
    if not raw_value:
        return None

    types = [value.strip() for value in raw_value.split(",") if value.strip()]
    invalid = [value for value in types if value not in VALID_RESULT_TYPES]
    if invalid:
        allowed = ", ".join(sorted(VALID_RESULT_TYPES))
        raise ValueError(f"invalid search types: {', '.join(invalid)}; allowed: {allowed}")
    return types or None


def _get_json_body() -> Dict[str, Any]:
    try:
        body = request.get_json(silent=False)
    except BadRequest as exc:
        raise ValueError("Request body must be valid JSON") from exc
    if body is None:
        raise ValueError("No JSON body provided")
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def _require_object_field(body: Dict[str, Any], field_name: str) -> Dict[str, Any] | None:
    value = body.get(field_name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"Field '{field_name}' must be an object")
    return value


# =============================================================================
# API Endpoints
# =============================================================================

@bp.route("", methods=["GET"])
def search_all():
    """Full-text search across all items.
    
    Query params:
        q: Search query (required)
        types: Comma-separated result types (optional)
        limit: Max results (default 20)
    
    Returns:
        {
            "success": true,
            "data": {
                "query": str,
                "results": [...],
                "total_count": int,
                "execution_time_ms": float
            }
        }
    """
    query = request.args.get("q", "").strip()
    if not query:
        return _error_response("Query parameter 'q' is required", 400)

    try:
        types = _parse_types(request.args.get("types", ""))
        limit = _parse_limit(request.args.get("limit", ""), default=20, max_value=100)
        engine = get_search_engine()
        response = engine.search(query, types, limit)
    except ValueError as exc:
        return _error_response(str(exc), 400)
    except Exception as exc:
        _LOGGER.error("Error performing search: %s", exc)
        return _error_response(str(exc), 500)

    return jsonify({
        "success": True,
        "data": {
            "query": response.query,
            "results": [
                {
                    "id": r.id,
                    "type": r.type,
                    "title": r.title,
                    "subtitle": r.subtitle,
                    "domain": r.domain,
                    "state": r.state,
                    "icon": r.icon,
                    "score": round(r.score, 2),
                    "metadata": r.metadata,
                }
                for r in response.results
            ],
            "total_count": response.total_count,
            "execution_time_ms": round(response.execution_time_ms, 2),
        }
    })


@bp.route("/entities", methods=["GET"])
def search_entities():
    """Filter entities by domain/state/area.
    
    Query params:
        domain: Filter by domain (optional)
        state: Filter by state (optional)
        area: Filter by area (optional)
        limit: Max results (default 50)
    """
    domain = request.args.get("domain")
    state = request.args.get("state")
    area = request.args.get("area")

    try:
        limit = _parse_limit(request.args.get("limit", ""), default=50, max_value=200)
        engine = get_search_engine()
        results = engine.filter_entities(domain, state, area, limit)
    except ValueError as exc:
        return _error_response(str(exc), 400)
    except Exception as exc:
        _LOGGER.error("Error filtering search entities: %s", exc)
        return _error_response(str(exc), 500)

    return jsonify({
        "success": True,
        "data": {
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "subtitle": r.subtitle,
                    "domain": r.domain,
                    "state": r.state,
                    "icon": r.icon,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "count": len(results),
        }
    })


@bp.route("/stats", methods=["GET"])
def get_search_stats():
    """Get search index statistics."""
    try:
        engine = get_search_engine()
        stats = engine.get_stats()
    except Exception as exc:
        _LOGGER.error("Error retrieving search stats: %s", exc)
        return _error_response(str(exc), 500)

    return jsonify({
        "success": True,
        "data": stats
    })


@bp.route("/index", methods=["POST"])
def update_search_index():
    """Update search index with HA data.
    
    JSON body:
        {
            "entities": {...},
            "automations": {...},
            "scripts": {...},
            "scenes": {...},
            "services": {...}
        }
    """
    try:
        body = _get_json_body()
        entities = _require_object_field(body, "entities")
        automations = _require_object_field(body, "automations")
        scripts = _require_object_field(body, "scripts")
        scenes = _require_object_field(body, "scenes")
        services = _require_object_field(body, "services")

        engine = get_search_engine()

        if entities is not None:
            engine.update_entities(entities)
        if automations is not None:
            engine.update_automations(automations)
        if scripts is not None:
            engine.update_scripts(scripts)
        if scenes is not None:
            engine.update_scenes(scenes)
        if services is not None:
            engine.update_services(services)

        stats = engine.get_stats()

        return jsonify({
            "success": True,
            "data": {
                "indexed": stats,
                "message": "Search index updated"
            }
        })
    except ValueError as exc:
        return _error_response(str(exc), 400)
    except Exception as exc:
        _LOGGER.error("Error updating search index: %s", exc)
        return _error_response(str(exc), 500)


__all__ = ["bp", "get_search_engine", "QuickSearchEngine"]


# ── SLICE 158: Search API Expansion ─────────────────────────────────

@bp.get("/advanced")
def search_advanced():
    """Advanced search with filters and facets.
    
    Query params:
    - q: Search query
    - types: Comma-separated entity types (optional)
    - zones: Comma-separated zone IDs (optional)
    - sort: relevance|name|date (default: relevance)
    - order: asc|desc (default: desc)
    - limit: Max results (default 20)
    - offset: Pagination offset (default 0)
    """
    from copilot_core.search.engine import get_search_engine
    
    query = request.args.get("q")
    if not query:
        return jsonify({
            "ok": False,
            "error": "Missing required parameter: q"
        }), 400
    
    types = request.args.get("types")
    type_list = [t.strip() for t in types.split(",")] if types else None
    
    zones = request.args.get("zones")
    zone_list = [z.strip() for z in zones.split(",")] if zones else None
    
    sort = request.args.get("sort", "relevance")
    order = request.args.get("order", "desc")
    
    try:
        limit = int(request.args.get("limit", "20"))
    except (ValueError, TypeError):
        limit = 20
    
    try:
        offset = int(request.args.get("offset", "0"))
    except (ValueError, TypeError):
        offset = 0
    
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    
    try:
        engine = get_search_engine()
        results = engine.advanced_search(
            query=query,
            types=type_list,
            zones=zone_list,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        _LOGGER.warning("Advanced search failed: %s", e)
        results = {"hits": [], "total": 0, "facets": {}}
    
    return jsonify({
        "ok": True,
        "query": query,
        "results": results,
        "count": len(results.get("hits", [])),
        "total": results.get("total", 0),
        "facets": results.get("facets", {}),
        "limit": limit,
        "offset": offset
    })


@bp.get("/history")
def search_history():
    """Get user search history.
    
    Query params:
    - limit: Max entries (default 20)
    - days: Days to look back (default 7)
    """
    from copilot_core.search.engine import get_search_engine
    
    try:
        limit = int(request.args.get("limit", "20"))
    except (ValueError, TypeError):
        limit = 20
    
    try:
        days = int(request.args.get("days", "7"))
    except (ValueError, TypeError):
        days = 7
    
    limit = max(1, min(limit, 100))
    days = max(1, min(days, 90))
    
    try:
        engine = get_search_engine()
        history = engine.get_history(limit=limit, days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get search history: %s", e)
        history = []
    
    return jsonify({
        "ok": True,
        "history": history,
        "count": len(history),
        "limit": limit,
        "days": days
    })


@bp.get("/analytics")
def search_analytics():
    """Get search analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.search.engine import get_search_engine
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        engine = get_search_engine()
        analytics = engine.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get search analytics: %s", e)
        analytics = {
            "total_searches": 0,
            "unique_queries": 0,
            "avg_results_per_query": 0.0,
            "no_result_queries": 0,
            "popular_queries": []
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/saved")
def search_saved():
    """Get saved searches.
    
    Query params:
    - user_id: User ID (optional, defaults to current user)
    """
    from copilot_core.search.engine import get_search_engine
    
    user_id = request.args.get("user_id")
    
    try:
        engine = get_search_engine()
        saved = engine.get_saved_searches(user_id=user_id)
    except Exception as e:
        _LOGGER.warning("Failed to get saved searches: %s", e)
        saved = []
    
    return jsonify({
        "ok": True,
        "saved": saved,
        "count": len(saved),
        "user_id": user_id or "current"
    })


@bp.post("/saved")
def search_save():
    """Save a search query.
    
    Body:
    - name: Name for the saved search
    - query: Search query to save
    - filters: Optional filter settings
    """
    data = request.get_json() or {}
    name = data.get("name")
    query = data.get("query")
    filters = data.get("filters", {})
    
    if not name or not query:
        return jsonify({
            "ok": False,
            "error": "Missing name or query"
        }), 400
    
    from copilot_core.search.engine import get_search_engine
    
    try:
        engine = get_search_engine()
        saved_id = engine.save_search(name=name, query=query, filters=filters)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to save search: %s", e)
        success = False
        saved_id = None
    
    return jsonify({
        "ok": success,
        "saved_id": saved_id,
        "name": name,
        "query": query
    })
