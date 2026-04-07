"""Harmonization API — Rules, Connections, and Statistics.

Endpoints for managing harmonization rules and module connections:
- GET /api/v1/harmonization/rules — Alle Rules
- GET /api/v1/harmonization/active — Aktive Connections
- POST /api/v1/harmonization/disable — Link deaktivieren
- GET /api/v1/harmonization/stats — Success-Rates
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

harmonization_bp = Blueprint("harmonization", __name__, url_prefix="/api/v1/harmonization")

# Global reference to rules engine (set during app initialization)
_rules_engine = None
_module_connections: List[Dict[str, Any]] = []


def set_rules_engine(engine) -> None:
    """Set the rules engine instance for API access."""
    global _rules_engine
    _rules_engine = engine
    logger.info("Harmonization API: Rules engine set")


def get_rules_engine():
    """Get the rules engine instance."""
    return _rules_engine


def set_module_connections(connections: List[Dict[str, Any]]) -> None:
    """Set module connections for API access."""
    global _module_connections
    _module_connections = connections
    logger.info("Harmonization API: %d module connections set", len(connections))


# =============================================================================
# GET /api/v1/harmonization/rules — Alle Rules
# =============================================================================

@harmonization_bp.route("/rules", methods=["GET"])
def get_rules():
    """Get all harmonization rules.
    
    Query Parameters:
        zone_id (optional): Filter by zone ID
        enabled (optional): Filter by enabled status (true/false)
        limit (optional): Limit results (default: 100)
    
    Returns:
        JSON response with rules array and metadata
    """
    zone_id = request.args.get("zone_id")
    enabled_param = request.args.get("enabled")
    limit = int(request.args.get("limit", 100))
    
    if not _rules_engine:
        return jsonify({
            "error": "Rules engine not initialized",
            "rules": [],
            "count": 0,
        }), 503
    
    try:
        # Get rules from engine
        enabled_only = None
        if enabled_param is not None:
            enabled_only = enabled_param.lower() == "true"
        
        rules = _rules_engine.get_rules(
            zone_id=zone_id if zone_id else None,
            enabled_only=enabled_only,
        )
        
        # Convert to dict and limit
        rules_data = [rule.to_dict() for rule in rules[:limit]]
        
        # Get statistics
        stats = _rules_engine.get_statistics()
        
        return jsonify({
            "rules": rules_data,
            "count": len(rules_data),
            "total": len(rules),
            "filtered": {
                "zone_id": zone_id,
                "enabled": enabled_param,
            },
            "metadata": {
                "total_rules": stats.get("total_rules", 0),
                "enabled_rules": stats.get("enabled_rules", 0),
                "disabled_rules": stats.get("disabled_rules", 0),
            },
        })
    
    except Exception as e:
        logger.exception("Error getting rules")
        return jsonify({
            "error": str(e),
            "rules": [],
            "count": 0,
        }), 500


# =============================================================================
# GET /api/v1/harmonization/active — Aktive Connections
# =============================================================================

@harmonization_bp.route("/active", methods=["GET"])
def get_active_connections():
    """Get active module connections.
    
    Returns all active connections between modules that are currently
    harmonizing data across the system.
    
    Returns:
        JSON response with active connections array
    """
    if not _rules_engine:
        return jsonify({
            "error": "Rules engine not initialized",
            "connections": [],
            "count": 0,
        }), 503
    
    try:
        # Get connections from rules engine
        connections = getattr(_rules_engine, '_connections', [])
        
        connections_data = []
        for conn in connections:
            if hasattr(conn, 'to_dict'):
                conn_dict = conn.to_dict()
            else:
                conn_dict = conn
            
            connections_data.append({
                **conn_dict,
                "active": True,
                "last_sync": datetime.now(timezone.utc).isoformat(),
            })
        
        # Also include module connections from global list
        for conn in _module_connections:
            if conn not in connections_data:
                connections_data.append({
                    **conn,
                    "active": True,
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                })
        
        return jsonify({
            "connections": connections_data,
            "count": len(connections_data),
            "modules": list(getattr(_rules_engine, '_modules', {}).keys()),
        })
    
    except Exception as e:
        logger.exception("Error getting active connections")
        return jsonify({
            "error": str(e),
            "connections": [],
            "count": 0,
        }), 500


# =============================================================================
# POST /api/v1/harmonization/disable — Link deaktivieren
# =============================================================================

@harmonization_bp.route("/disable", methods=["POST"])
def disable_link():
    """Disable a harmonization link (rule or connection).
    
    Request Body:
        type (required): "rule" or "connection"
        id (required): rule_id or connection_id
        reason (optional): Reason for disabling
    
    Returns:
        JSON response with success status and details
    """
    if not _rules_engine:
        return jsonify({
            "error": "Rules engine not initialized",
        }), 503
    
    try:
        data = request.get_json() or {}
        
        link_type = data.get("type")
        link_id = data.get("id")
        reason = data.get("reason", "Manual disable via API")
        
        if not link_type or not link_id:
            return jsonify({
                "error": "Missing required fields: type and id",
                "success": False,
            }), 400
        
        if link_type not in ["rule", "connection"]:
            return jsonify({
                "error": "Invalid type. Must be 'rule' or 'connection'",
                "success": False,
            }), 400
        
        if link_type == "rule":
            # Disable rule
            success = _rules_engine.disable_rule(link_id)
            
            if success:
                rule = _rules_engine.get_rule(link_id)
                return jsonify({
                    "success": True,
                    "type": "rule",
                    "id": link_id,
                    "name": rule.name if rule else link_id,
                    "disabled_at": datetime.now(timezone.utc).isoformat(),
                    "reason": reason,
                    "message": f"Rule '{link_id}' disabled successfully",
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Rule '{link_id}' not found",
                }), 404
        
        elif link_type == "connection":
            # Disable connection (remove from active list)
            connections = getattr(_rules_engine, '_connections', [])
            
            # Find and mark connection as inactive
            for conn in connections:
                conn_dict = conn.to_dict() if hasattr(conn, 'to_dict') else conn
                if conn_dict.get('source_module') == link_id or \
                   conn_dict.get('target_module') == link_id or \
                   conn_dict.get('id') == link_id:
                    # Mark as disabled
                    conn_dict['active'] = False
                    conn_dict['disabled_at'] = datetime.now(timezone.utc).isoformat()
                    conn_dict['reason'] = reason
                    
                    return jsonify({
                        "success": True,
                        "type": "connection",
                        "id": link_id,
                        "disabled_at": datetime.now(timezone.utc).isoformat(),
                        "reason": reason,
                        "message": f"Connection '{link_id}' disabled successfully",
                    })
            
            return jsonify({
                "success": False,
                "error": f"Connection '{link_id}' not found",
            }), 404
    
    except Exception as e:
        logger.exception("Error disabling link")
        return jsonify({
            "error": str(e),
            "success": False,
        }), 500


# =============================================================================
# GET /api/v1/harmonization/stats — Success-Rates
# =============================================================================

@harmonization_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get harmonization statistics and success rates.
    
    Query Parameters:
        period (optional): Time period in hours (default: 24)
        rule_id (optional): Filter by specific rule ID
    
    Returns:
        JSON response with statistics including success rates, execution counts, etc.
    """
    period_hours = int(request.args.get("period", 24))
    rule_id = request.args.get("rule_id")
    
    if not _rules_engine:
        return jsonify({
            "error": "Rules engine not initialized",
        }), 503
    
    try:
        # Get base statistics
        stats = _rules_engine.get_statistics()
        
        # Get executions for detailed stats
        executions = _rules_engine.get_executions(
            rule_id=rule_id if rule_id else None,
            limit=1000,
        )
        
        # Calculate success rates
        total_executions = len(executions)
        successful = len([e for e in executions if e.success])
        failed = total_executions - successful
        
        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0.0
        
        # Calculate per-rule statistics
        rule_stats = {}
        for rule in _rules_engine.get_rules():
            rule_execs = [e for e in executions if e.rule_id == rule.rule_id]
            rule_success = len([e for e in rule_execs if e.success])
            rule_total = len(rule_execs)
            
            rule_stats[rule.rule_id] = {
                "name": rule.name,
                "total_executions": rule_total,
                "successful": rule_success,
                "failed": rule_total - rule_success,
                "success_rate": (rule_success / rule_total * 100) if rule_total > 0 else 0.0,
                "trigger_count": rule.trigger_count,
                "last_triggered": rule.last_triggered,
                "enabled": rule.enabled,
            }
        
        # Calculate connection statistics
        connections = getattr(_rules_engine, '_connections', [])
        connection_stats = {
            "total_connections": len(connections),
            "active_connections": len([c for c in connections]),
            "total_applied": getattr(_rules_engine, '_connections_applied', 0),
        }
        
        # Time range
        now = datetime.now(timezone.utc)
        time_range = {
            "start": (now.replace(hour=0, minute=0, second=0, microsecond=0)).isoformat(),
            "end": now.isoformat(),
            "period_hours": period_hours,
        }
        
        return jsonify({
            "summary": {
                "total_rules": stats.get("total_rules", 0),
                "enabled_rules": stats.get("enabled_rules", 0),
                "disabled_rules": stats.get("disabled_rules", 0),
                "total_executions": total_executions,
                "successful_executions": successful,
                "failed_executions": failed,
                "overall_success_rate": round(success_rate, 2),
                "triggered_rules": stats.get("triggered_rules", 0),
                "registered_modules": stats.get("registered_modules", 0),
            },
            "connections": connection_stats,
            "rules": rule_stats,
            "time_range": time_range,
            "generated_at": now.isoformat(),
        })
    
    except Exception as e:
        logger.exception("Error getting statistics")
        return jsonify({
            "error": str(e),
        }), 500


# =============================================================================
# Additional helper endpoints
# =============================================================================

@harmonization_bp.route("/rules/<rule_id>", methods=["GET"])
def get_rule(rule_id: str):
    """Get a specific rule by ID."""
    if not _rules_engine:
        return jsonify({"error": "Rules engine not initialized"}), 503
    
    rule = _rules_engine.get_rule(rule_id)
    
    if not rule:
        return jsonify({"error": f"Rule '{rule_id}' not found"}), 404
    
    return jsonify({
        "rule": rule.to_dict(),
    })


@harmonization_bp.route("/rules/<rule_id>/enable", methods=["POST"])
def enable_rule(rule_id: str):
    """Enable a specific rule."""
    if not _rules_engine:
        return jsonify({"error": "Rules engine not initialized"}), 503
    
    success = _rules_engine.enable_rule(rule_id)
    
    if success:
        rule = _rules_engine.get_rule(rule_id)
        return jsonify({
            "success": True,
            "rule_id": rule_id,
            "name": rule.name if rule else rule_id,
            "enabled_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Rule '{rule_id}' not found",
        }), 404


@harmonization_bp.route("/executions", methods=["GET"])
def get_executions():
    """Get recent rule executions."""
    if not _rules_engine:
        return jsonify({"error": "Rules engine not initialized"}), 503
    
    rule_id = request.args.get("rule_id")
    limit = int(request.args.get("limit", 50))
    
    executions = _rules_engine.get_executions(rule_id=rule_id, limit=limit)
    
    return jsonify({
        "executions": [e.to_dict() for e in executions],
        "count": len(executions),
    })


__all__ = [
    "harmonization_bp",
    "set_rules_engine",
    "get_rules_engine",
    "set_module_connections",
]
