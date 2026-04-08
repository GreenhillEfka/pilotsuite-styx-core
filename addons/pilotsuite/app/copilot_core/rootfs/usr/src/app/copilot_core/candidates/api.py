"""
Candidate Management API - REST endpoints for automation suggestion lifecycle.

Endpoints:
    GET  /api/v1/candidates         - List candidates with optional filters
    POST /api/v1/candidates         - Create candidate from pattern discovery  
    GET  /api/v1/candidates/{id}    - Get specific candidate details
    PUT  /api/v1/candidates/{id}    - Update candidate state (accept/dismiss/defer)
    GET  /api/v1/candidates/stats   - Storage statistics and health
"""
from __future__ import annotations

import time
from flask import Blueprint, request, jsonify, Response
from typing import Dict, Any

from .store import CandidateStore, CandidateState
from ..api.security import require_api_key

# Create blueprint
candidates_bp = Blueprint('candidates_svc', __name__, url_prefix='/api/v1/candidates')

# Global store instance (will be initialized in main.py)
_candidate_store: CandidateStore = None

def init_candidates_api(store: CandidateStore = None):
    """Initialize the candidates API with store instance."""
    global _candidate_store
    _candidate_store = store or CandidateStore()

def get_store() -> CandidateStore:
    """Get or create the global candidate store."""
    global _candidate_store
    if _candidate_store is None:
        _candidate_store = CandidateStore()
    return _candidate_store

@candidates_bp.route('', methods=['GET'])
@require_api_key
def list_candidates() -> Response:
    """
    List candidates with optional filters.
    
    Query parameters:
    - state: filter by state (pending, offered, accepted, dismissed, deferred)
    - include_ready_deferred: include deferred candidates ready for retry (true/false)
    - limit: max results (default 50, max 200)
    """
    try:
        store = get_store()
        
        # Parse query parameters
        state = request.args.get('state')
        if state and state not in ['pending', 'offered', 'accepted', 'dismissed', 'deferred']:
            return jsonify({"error": f"Invalid state: {state}"}), 400
        
        include_ready_deferred = request.args.get('include_ready_deferred', 'false').lower() == 'true'
        limit = min(int(request.args.get('limit', 50)), 200)
        
        # Get candidates
        candidates = store.list_candidates(
            state=state, 
            include_ready_deferred=include_ready_deferred
        )
        
        # Apply limit
        candidates = candidates[:limit]
        
        # Serialize
        result = {
            "candidates": [c.to_dict() for c in candidates],
            "count": len(candidates),
            "filters": {
                "state": state,
                "include_ready_deferred": include_ready_deferred,
                "limit": limit
            }
        }
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@candidates_bp.route('', methods=['POST'])
@require_api_key
def create_candidate() -> Response:
    """
    Create new candidate from pattern discovery.
    
    Expected body:
    {
        "pattern_id": "pattern-uuid-from-brain-graph",
        "evidence": {
            "support": 0.85,
            "confidence": 0.92, 
            "lift": 3.2,
            "pattern_type": "temporal_sequence"
        },
        "metadata": {
            "source": "habitus_miner",
            "trigger_entity": "binary_sensor.front_door",
            "target_entity": "light.hallway"
        }
    }
    """
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "Invalid JSON body"}), 400
        
        # Validate required fields
        pattern_id = body.get('pattern_id')
        if not pattern_id:
            return jsonify({"error": "Missing required field: pattern_id"}), 400
        
        evidence = body.get('evidence', {})
        if not isinstance(evidence, dict):
            return jsonify({"error": "Evidence must be an object"}), 400
        
        metadata = body.get('metadata', {})
        if not isinstance(metadata, dict):
            return jsonify({"error": "Metadata must be an object"}), 400
        
        # Create candidate
        store = get_store()
        candidate_id = store.add_candidate(
            pattern_id=pattern_id,
            evidence=evidence,
            metadata=metadata
        )
        
        # Return created candidate
        candidate = store.get_candidate(candidate_id)
        return jsonify({
            "created": True,
            "candidate": candidate.to_dict()
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@candidates_bp.route('/<candidate_id>', methods=['GET'])
@require_api_key
def get_candidate(candidate_id: str) -> Response:
    """Get specific candidate details by ID."""
    try:
        store = get_store()
        candidate = store.get_candidate(candidate_id)
        
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404
        
        return jsonify(candidate.to_dict())
        
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@candidates_bp.route('/<candidate_id>', methods=['PUT'])
@require_api_key
def update_candidate(candidate_id: str) -> Response:
    """
    Update candidate state.
    
    Expected body:
    {
        "state": "accepted|dismissed|deferred|offered",
        "retry_after_days": 7  // Optional, only for deferred state
    }
    """
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "Invalid JSON body"}), 400
        
        # Validate state
        new_state = body.get('state')
        if new_state not in ['pending', 'offered', 'accepted', 'dismissed', 'deferred']:
            return jsonify({"error": f"Invalid state: {new_state}"}), 400
        
        # Calculate retry_after for deferred candidates
        retry_after = None
        if new_state == 'deferred':
            retry_after_days = body.get('retry_after_days', 7)
            try:
                retry_after_days = float(retry_after_days)
                if retry_after_days <= 0:
                    raise ValueError("retry_after_days must be positive")
                retry_after = time.time() + (retry_after_days * 24 * 60 * 60)
            except (ValueError, TypeError):
                return jsonify({"error": "retry_after_days must be a positive number"}), 400
        
        # Update candidate
        store = get_store()
        success = store.update_candidate_state(
            candidate_id=candidate_id,
            new_state=new_state,
            retry_after=retry_after
        )
        
        if not success:
            return jsonify({"error": "Candidate not found"}), 404
        
        # Return updated candidate
        candidate = store.get_candidate(candidate_id)
        return jsonify({
            "updated": True,
            "candidate": candidate.to_dict()
        })
        
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@candidates_bp.route('/stats', methods=['GET'])
@require_api_key
def get_candidates_stats() -> Response:
    """Get candidate storage statistics and health metrics."""
    try:
        store = get_store()
        stats = store.get_stats()
        
        # Add timestamp
        stats['generated_at'] = time.time()
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@candidates_bp.route('/cleanup', methods=['POST'])
@require_api_key
def cleanup_old_candidates() -> Response:
    """Remove old dismissed/accepted candidates."""
    try:
        body = request.get_json(silent=True) or {}
        max_age_days = body.get('max_age_days', 30)
        
        # Validate
        try:
            max_age_days = int(max_age_days)
            if max_age_days <= 0:
                raise ValueError("max_age_days must be positive")
        except (ValueError, TypeError):
            return jsonify({"error": "max_age_days must be a positive integer"}), 400
        
        # Cleanup
        store = get_store()
        removed_count = store.cleanup_old_candidates(max_age_days)
        
        return jsonify({
            "cleaned_up": True,
            "removed_count": removed_count,
            "max_age_days": max_age_days
        })
        
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500