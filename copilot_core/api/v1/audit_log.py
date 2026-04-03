"""Audit Log API — Slice 69"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from ...audit.contracts import (
    AuditEventType,
    AuditLogEntryV1,
    AuditLogSummaryV1,
    AuditOutcome,
    AuditSeverity,
)
from ...audit.store import AuditLogStore
from ...core.security import require_auth

audit_bp = Blueprint("audit", __name__, url_prefix="/api/v1/audit")

_store: Optional[AuditLogStore] = None


def init_audit_api(store: AuditLogStore) -> None:
    """Initialize audit API with store instance."""
    global _store
    _store = store


def _get_store() -> AuditLogStore:
    if _store is None:
        raise RuntimeError("Audit store not initialized")
    return _store


@audit_bp.route("/logs", methods=["GET"])
@require_auth()
def list_logs() -> Any:
    """List audit log entries with filters."""
    try:
        store = _get_store()
        entries = store.get_entries(
            limit=min(int(request.args.get("limit", 100)), 500),
            offset=int(request.args.get("offset", 0)),
            zone_id=request.args.get("zone_id"),
            module_id=request.args.get("module_id"),
            event_type=request.args.get("event_type"),
            outcome=request.args.get("outcome"),
            severity=request.args.get("severity"),
            user_id=request.args.get("user_id"),
            proposal_id=request.args.get("proposal_id"),
            action_closure_id=request.args.get("action_closure_id"),
            correlation_id=request.args.get("correlation_id"),
            since=request.args.get("since"),
            until=request.args.get("until"),
            order_by=request.args.get("order_by", "created_at"),
            order=request.args.get("order", "DESC"),
        )
        return jsonify(
            {
                "entries": [
                    {
                        k: v
                        for k, v in entry.__dict__.items()
                        if not k.startswith("_")
                    }
                    for entry in entries
                ],
                "count": len(entries),
                "revision": store.get_revision(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audit_bp.route("/logs/<entry_id>", methods=["GET"])
@require_auth()
def get_log_entry(entry_id: str) -> Any:
    """Get a single audit log entry."""
    try:
        store = _get_store()
        entry = store.get_entry(entry_id)
        if not entry:
            return jsonify({"error": "Entry not found"}), 404
        return jsonify({k: v for k, v in entry.__dict__.items() if not k.startswith("_")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audit_bp.route("/logs/delta", methods=["GET"])
@require_auth()
def get_logs_delta() -> Any:
    """Get audit log delta since revision (for incremental polling)."""
    try:
        store = _get_store()
        since_revision = int(request.args.get("since_revision", 0))
        limit = min(int(request.args.get("limit", 100)), 500)

        delta = store.get_delta(since_revision, limit)
        return jsonify(
            {
                "revision": delta.revision,
                "has_changes": delta.has_changes,
                "entries": [
                    {k: v for k, v in e.__dict__.items() if not k.startswith("_")}
                    for e in delta.new_entries
                ],
                "latest_entry_at": delta.latest_entry_at,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audit_bp.route("/summary", methods=["GET"])
@require_auth()
def get_summary() -> Any:
    """Get audit log summary with aggregations."""
    try:
        store = _get_store()
        summary = store.get_summary(
            zone_id=request.args.get("zone_id"),
            module_id=request.args.get("module_id"),
            event_type=request.args.get("event_type"),
            outcome=request.args.get("outcome"),
            severity=request.args.get("severity"),
            since=request.args.get("since"),
            until=request.args.get("until"),
            recent_limit=min(int(request.args.get("recent_limit", 10)), 50),
        )
        return jsonify(
            {
                "total_entries": summary.total_entries,
                "revision": summary.revision,
                "latest_entry_at": summary.latest_entry_at,
                "earliest_entry_at": summary.earliest_entry_at,
                "outcomes": {
                    "success": summary.success_count,
                    "failure": summary.failure_count,
                    "pending": summary.pending_count,
                    "cancelled": summary.cancelled_count,
                    "skipped": summary.skipped_count,
                },
                "severities": {
                    "debug": summary.debug_count,
                    "info": summary.info_count,
                    "warning": summary.warning_count,
                    "error": summary.error_count,
                    "critical": summary.critical_count,
                },
                "event_type_counts": summary.event_type_counts,
                "recent_entries": [
                    {k: v for k, v in e.__dict__.items() if not k.startswith("_")}
                    for e in summary.recent_entries
                ],
                "filters": {
                    "zone_id": summary.zone_id,
                    "module_id": summary.module_id,
                    "event_type": summary.event_type,
                    "outcome": summary.outcome,
                    "severity": summary.severity,
                    "since": summary.since,
                    "until": summary.until,
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audit_bp.route("/export", methods=["POST"])
@require_auth()
def export_logs() -> Any:
    """Export audit logs to file."""
    try:
        store = _get_store()
        data = request.get_json() or {}
        export_id = data.get("export_id", str(uuid.uuid4()))
        format = data.get("format", "json")
        filters = data.get("filters", {})

        if format not in ("json", "csv", "ndjson"):
            return jsonify({"error": "Invalid format. Use json, csv, or ndjson"}), 400

        path, count = store.export_entries(export_id, format, filters)
        return jsonify(
            {
                "export_id": export_id,
                "format": format,
                "path": path,
                "entry_count": count,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audit_bp.route("/ingest", methods=["POST"])
@require_auth()
def ingest_event() -> Any:
    """Manually ingest an audit event (for external systems)."""
    try:
        store = _get_store()
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        # Validate required fields
        required = ["event_type", "outcome", "severity", "subject"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validate enums
        try:
            event_type = AuditEventType(data["event_type"])
        except ValueError:
            return jsonify(
                {"error": f"Invalid event_type. Valid values: {[e.value for e in AuditEventType]}"}
            ), 400

        try:
            outcome = AuditOutcome(data["outcome"])
        except ValueError:
            return jsonify(
                {"error": f"Invalid outcome. Valid values: {[o.value for o in AuditOutcome]}"}
            ), 400

        try:
            severity = AuditSeverity(data["severity"])
        except ValueError:
            return jsonify(
                {"error": f"Invalid severity. Valid values: {[s.value for s in AuditSeverity]}"}
            ), 400

        entry = AuditLogEntryV1.from_event(
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            event_type=event_type,
            outcome=outcome,
            severity=severity,
            subject=data["subject"],
            details=data.get("details", {}),
            metadata=data.get("metadata", {}),
            zone_id=data.get("zone_id"),
            module_id=data.get("module_id"),
            proposal_id=data.get("proposal_id"),
            action_closure_id=data.get("action_closure_id"),
            notification_id=data.get("notification_id"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            parent_entry_id=data.get("parent_entry_id"),
            correlation_id=data.get("correlation_id"),
            duration_ms=data.get("duration_ms"),
        )

        stored_entry = store.add_entry(entry)
        return jsonify(
            {k: v for k, v in stored_entry.__dict__.items() if not k.startswith("_")}
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audit_bp.route("/revision", methods=["GET"])
@require_auth()
def get_revision() -> Any:
    """Get current audit log revision."""
    try:
        store = _get_store()
        return jsonify({"revision": store.get_revision()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
