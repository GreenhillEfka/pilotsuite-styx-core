"""
Insights API v1 for PilotSuite Core.

Provides REST endpoints for querying and managing insights.
"""

from flask import Blueprint, jsonify, request
from typing import Optional

from ...insights.contracts import (
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    InsightSource,
)
from ...insights.store import InsightStore
from ...insights.generators import run_all_generators


def create_insights_blueprint(insight_store: InsightStore):
    """Create Flask blueprint for insights API."""
    bp = Blueprint("insights", __name__, url_prefix="/api/v1/insights")
    
    @bp.route("", methods=["GET"])
    def list_insights():
        """
        List insights with optional filters.
        
        Query params:
        - category: filter by category
        - severity: filter by severity
        - status: filter by status
        - source: filter by source
        - zone_id: filter by zone
        - since_revision: only return insights with revision > value
        - limit: max results (default 100)
        """
        category = request.args.get("category")
        severity = request.args.get("severity")
        status = request.args.get("status")
        source = request.args.get("source")
        zone_id = request.args.get("zone_id")
        since_revision = request.args.get("since_revision", type=int)
        limit = request.args.get("limit", default=100, type=int)
        
        try:
            category_enum = InsightCategory(category) if category else None
        except ValueError:
            return jsonify({"error": f"Invalid category: {category}"}), 400
        
        try:
            severity_enum = InsightSeverity(severity) if severity else None
        except ValueError:
            return jsonify({"error": f"Invalid severity: {severity}"}), 400
        
        try:
            status_enum = InsightStatus(status) if status else None
        except ValueError:
            return jsonify({"error": f"Invalid status: {status}"}), 400
        
        try:
            source_enum = InsightSource(source) if source else None
        except ValueError:
            return jsonify({"error": f"Invalid source: {source}"}), 400
        
        insights = insight_store.get_insights(
            category=category_enum,
            severity=severity_enum,
            status=status_enum,
            source=source_enum,
            zone_id=zone_id,
            since_revision=since_revision,
            limit=limit,
        )
        
        return jsonify({
            "insights": [i.to_dict() for i in insights],
            "count": len(insights),
        })
    
    @bp.route("/<insight_id>", methods=["GET"])
    def get_insight(insight_id: str):
        """Get a single insight by ID."""
        insight = insight_store.get_insight(insight_id)
        
        if not insight:
            return jsonify({"error": "Insight not found"}), 404
        
        return jsonify(insight.to_dict())
    
    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """
        Get summary of insights with counts.
        
        Query params:
        - since_revision: compute summary for changes since this revision
        """
        since_revision = request.args.get("since_revision", type=int)
        
        summary = insight_store.get_summary(since_revision=since_revision)
        
        return jsonify(summary.to_dict())
    
    @bp.route("/delta", methods=["GET"])
    def get_delta():
        """
        Get delta information for polling.
        
        Query params:
        - since_revision (required): revision to compare against
        """
        since_revision = request.args.get("since_revision", type=int)
        
        if since_revision is None:
            return jsonify({"error": "since_revision is required"}), 400
        
        delta = insight_store.get_delta(since_revision)
        
        return jsonify(delta.to_dict())
    
    @bp.route("/<insight_id>/status", methods=["PUT"])
    def update_status(insight_id: str):
        """
        Update the status of an insight.
        
        Body:
        - status: new status (new|acknowledged|in_progress|resolved|dismissed)
        """
        data = request.get_json()
        
        if not data or "status" not in data:
            return jsonify({"error": "status is required"}), 400
        
        try:
            new_status = InsightStatus(data["status"])
        except ValueError:
            return jsonify({"error": f"Invalid status: {data['status']}"}), 400
        
        updated = insight_store.update_insight_status(insight_id, new_status)
        
        if not updated:
            return jsonify({"error": "Insight not found"}), 404
        
        return jsonify(updated.to_dict())
    
    @bp.route("/generate", methods=["POST"])
    def generate_insights():
        """
        Run insight generators and add new insights.
        
        This is typically called by a scheduled job or manually triggered.
        """
        new_insights = run_all_generators(insight_store)
        
        for insight in new_insights:
            insight_store.add_insight(insight)
        
        return jsonify({
            "generated": len(new_insights),
            "insights": [i.to_dict() for i in new_insights],
        })
    
    @bp.route("/categories", methods=["GET"])
    def list_categories():
        """List all available insight categories."""
        return jsonify({
            "categories": [c.value for c in InsightCategory],
        })
    
    @bp.route("/severities", methods=["GET"])
    def list_severities():
        """List all available severity levels."""
        return jsonify({
            "severities": [s.value for s in InsightSeverity],
        })
    
    @bp.route("/statuses", methods=["GET"])
    def list_statuses():
        """List all available insight statuses."""
        return jsonify({
            "statuses": [s.value for s in InsightStatus],
        })
    
    @bp.route("/sources", methods=["GET"])
    def list_sources():
        """List all available insight sources."""
        return jsonify({
            "sources": [s.value for s in InsightSource],
        })
    
    return bp
