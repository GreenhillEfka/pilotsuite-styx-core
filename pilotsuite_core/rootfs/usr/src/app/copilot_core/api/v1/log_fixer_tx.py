"""
API v1 Blueprint - log_fixer_tx
Transaction Log Audit & Management
"""
from flask import Blueprint, jsonify, request
from copilot_core.api.security import require_api_key
from copilot_core.log_fixer_tx.recovery import TransactionManager

bp = Blueprint('log_fixer_tx', __name__, url_prefix='/api/v1/log_fixer_tx')

# Global transaction manager instance
tx_manager = TransactionManager()


@bp.route('/status', methods=['GET'])
@require_api_key
def get_status():
    """
    Get log_fixer_tx status and capabilities.
    
    GET /api/v1/log_fixer_tx/status
    
    Returns:
        {
            "enabled": true,
            "version": "0.1.0",
            "capabilities": ["rename", "set_enabled", "audit", "rollback"]
        }
    """
    return jsonify({
        "enabled": True,
        "version": "0.1.0",
        "capabilities": ["rename", "set_enabled", "audit", "rollback"],
        "log_path": str(tx_manager.log.log_path),
    })


@bp.route('/transactions', methods=['GET'])
@require_api_key
def list_transactions():
    """
    List all transactions with their states.
    
    GET /api/v1/log_fixer_tx/transactions?state=in-flight
    
    Query params:
        state: Filter by state (in-flight|applied|failed|rolled_back|aborted)
        limit: Max number of results (default: 100)
        
    Returns:
        {
            "transactions": [
                {
                    "tx_id": "...",
                    "state": "applied",
                    "timestamp": "2026-02-09T21:40:00Z",
                    "actor": {...},
                    "reason": "...",
                    "operation_count": 2
                }
            ]
        }
    """
    state_filter = request.args.get('state')
    limit = int(request.args.get('limit', 100))
    
    transactions = tx_manager.list_transactions()
    
    # Apply filter
    if state_filter:
        transactions = [t for t in transactions if t['state'] == state_filter]
        
    # Apply limit
    transactions = transactions[-limit:]
    
    return jsonify({
        "transactions": transactions,
        "count": len(transactions),
    })


@bp.route('/transactions/<tx_id>', methods=['GET'])
@require_api_key
def get_transaction(tx_id):
    """
    Get detailed information about a specific transaction.
    
    GET /api/v1/log_fixer_tx/transactions/<tx_id>
    
    Returns:
        {
            "tx_id": "...",
            "state": "applied",
            "records": [...]
        }
    """
    records = tx_manager.log.get_tx_records(tx_id)
    
    if not records:
        return jsonify({"error": "Transaction not found"}), 404
        
    state = tx_manager.log.get_tx_state(tx_id)
    
    return jsonify({
        "tx_id": tx_id,
        "state": state,
        "records": records,
        "record_count": len(records),
    })


@bp.route('/transactions/<tx_id>/rollback', methods=['POST'])
@require_api_key
def rollback_transaction(tx_id):
    """
    Manually rollback a transaction.
    
    POST /api/v1/log_fixer_tx/transactions/<tx_id>/rollback
    
    Body:
        {
            "reason": "Manual rollback requested"
        }
        
    Returns:
        {
            "tx_id": "...",
            "success": true
        }
    """
    data = request.get_json() or {}
    reason = data.get('reason', 'Manual rollback via API')
    
    # Check if transaction exists
    state = tx_manager.log.get_tx_state(tx_id)
    if state == "unknown":
        return jsonify({"error": "Transaction not found"}), 404
        
    # Check if already rolled back
    if state == "rolled_back":
        return jsonify({
            "tx_id": tx_id,
            "success": True,
            "message": "Already rolled back",
        })
        
    # Perform rollback
    result = tx_manager.rollback_tx(tx_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500


@bp.route('/recover', methods=['POST'])
@require_api_key
def recover():
    """
    Manually trigger recovery (rollback in-flight transactions).
    
    POST /api/v1/log_fixer_tx/recover
    
    Returns:
        {
            "in_flight_count": 2,
            "rolled_back_count": 2,
            "failed_count": 0,
            "in_flight_tx": ["..."],
            "rolled_back_tx": ["..."],
            "failed_tx": []
        }
    """
    report = tx_manager.recover()
    return jsonify(report.to_dict())


@bp.route('/transactions', methods=['POST'])
@require_api_key
def create_transaction():
    """
    Create and execute a new transaction (convenience endpoint).
    
    POST /api/v1/log_fixer_tx/transactions
    
    Body:
        {
            "actor": {
                "service": "ha_copilot",
                "user": "admin",
                "host": "..."
            },
            "reason": "Rename config file",
            "operations": [
                {
                    "kind": "rename",
                    "target": "/data/config.yaml",
                    "before": {"path": "/data/old_config.yaml"},
                    "after": {"path": "/data/config.yaml"}
                }
            ]
        }
        
    Returns:
        {
            "tx_id": "...",
            "success": true,
            "results": [...]
        }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
        
    actor = data.get('actor')
    reason = data.get('reason')
    operations = data.get('operations', [])
    
    if not actor:
        return jsonify({"error": "actor required"}), 400
        
    if not operations:
        return jsonify({"error": "operations required"}), 400
        
    # Begin transaction
    tx_id = tx_manager.begin_tx(actor, reason)
    
    # Append intents
    for seq, op in enumerate(operations, start=1):
        # Add inverse to operation
        if op['kind'] == 'rename':
            op['inverse'] = {
                'kind': 'rename',
                'target': op['target'],
                'before': op['after'],
                'after': op['before'],
            }
        elif op['kind'] == 'set_enabled':
            op['inverse'] = {
                'kind': 'set_enabled',
                'target': op['target'],
                'before': op['after'],
                'after': op['before'],
            }
            
        tx_manager.append_intent(tx_id, seq, actor, op, reason)
        
    # Apply transaction
    result = tx_manager.apply_tx(tx_id)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 500
