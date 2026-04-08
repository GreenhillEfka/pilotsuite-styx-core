"""
Flask Wrapper für Dialog State API (Slice 74)

Kompatibilitätsschicht zwischen FastAPI dialog_state.py und Flask Addon
"""

from flask import Blueprint, request, jsonify
import sys
import os

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from copilot_core.voice.dialog_state import get_dialog_machine

bp = Blueprint('voice', __name__, url_prefix='/api/v1/voice')


@bp.route('/dialog/state', methods=['GET'])
def get_dialog_state():
    """Get current dialog state"""
    machine = get_dialog_machine()
    state = machine.get_state()
    timeout = machine.check_timeout()
    
    if timeout:
        machine.decay()
    
    return jsonify({
        'state': state.state,
        'active_intent': state.active_intent,
        'slot_values': state.slot_values,
        'context_stack_size': len(state.context_stack),
        'timeout': timeout,
        'confirmation_question': machine.generate_confirmation_question(),
        'clarification_question': machine.generate_clarification_question(),
    })


@bp.route('/dialog/activate', methods=['POST'])
def activate_intent():
    """Activate new intent"""
    data = request.get_json() or {}
    machine = get_dialog_machine()
    
    state = machine.activate_intent(
        intent=data.get('intent', ''),
        slots=data.get('slots', {}),
        session_id=data.get('session_id'),
        user_id=data.get('user_id'),
    )
    
    return jsonify({
        'state': state.state,
        'active_intent': state.active_intent,
        'slot_values': state.slot_values,
    })


@bp.route('/dialog/confirm', methods=['POST'])
def confirm_action():
    """User confirms pending action"""
    data = request.get_json() or {}
    machine = get_dialog_machine()
    
    if data.get('confirmed', True):
        state = machine.confirm_action()
    else:
        state = machine.cancel_action()
    
    return jsonify({
        'state': state.state,
        'active_intent': state.active_intent,
    })


@bp.route('/dialog/cancel', methods=['POST'])
def cancel_action():
    """User cancels pending action"""
    machine = get_dialog_machine()
    state = machine.cancel_action()
    
    return jsonify({
        'state': state.state,
        'active_intent': state.active_intent,
    })


@bp.route('/dialog/clarify', methods=['POST'])
def clarify_dialog():
    """Set clarification question"""
    data = request.get_json() or {}
    machine = get_dialog_machine()
    
    state = machine.set_clarifying(data.get('clarification_text', ''))
    
    return jsonify({
        'state': state.state,
        'clarification_question': machine.generate_clarification_question(),
    })


@bp.route('/dialog/timeout', methods=['POST'])
def check_timeout():
    """Check dialog timeout"""
    machine = get_dialog_machine()
    timed_out = machine.check_timeout()
    
    if timed_out:
        machine.decay()
    
    return jsonify({
        'timed_out': timed_out,
        'state': machine.get_state().state,
    })


@bp.route('/dialog/reset', methods=['POST'])
def reset_dialog():
    """Reset dialog to IDLE"""
    machine = get_dialog_machine()
    machine.reset()
    
    return jsonify({'state': 'IDLE'})
