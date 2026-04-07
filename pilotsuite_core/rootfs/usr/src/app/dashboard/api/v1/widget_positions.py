"""
PilotSuite Styx Dashboard API v1 - Widget Positions
Endpoints for saving and retrieving widget positions
"""
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import threading
import json
import os

widget_positions_bp = Blueprint('widget_positions_v1', __name__, url_prefix='/api/v1/widgets/positions')

# In-Memory Storage für Widget-Positionen (wird durch persistenten Storage ersetzt)
widget_positions_store = {}
positions_lock = threading.Lock()

# Pfad für persistente Speicherung
POSITIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data',
    'widget_positions.json'
)


def load_positions_from_file():
    """Positionen aus Datei laden"""
    global widget_positions_store
    try:
        if os.path.exists(POSITIONS_FILE):
            with open(POSITIONS_FILE, 'r') as f:
                widget_positions_store = json.load(f)
            print(f'[WidgetPositions] Loaded {len(widget_positions_store)} positions from file')
    except Exception as e:
        print(f'[WidgetPositions] Error loading positions: {e}')
        widget_positions_store = {}


def save_positions_to_file():
    """Positionen in Datei speichern"""
    try:
        os.makedirs(os.path.dirname(POSITIONS_FILE), exist_ok=True)
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(widget_positions_store, f, indent=2)
        print(f'[WidgetPositions] Saved {len(widget_positions_store)} positions to file')
    except Exception as e:
        print(f'[WidgetPositions] Error saving positions: {e}')


@widget_positions_bp.route('', methods=['GET'])
def get_all_positions():
    """
    Alle Widget-Positionen abrufen
    """
    with positions_lock:
        return jsonify({
            'positions': widget_positions_store,
            'total': len(widget_positions_store),
            'last_update': max(
                (pos.get('last_update') for pos in widget_positions_store.values()),
                default=None
            )
        })


@widget_positions_bp.route('', methods=['POST'])
def save_position():
    """
    Neue Widget-Position speichern
    Erwartet: { "widget_id": "...", "x": 0, "y": 0, "width": 1, "height": 1, "zone_id": "..." }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['widget_id', 'x', 'y']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    widget_id = data['widget_id']
    
    # Position validieren
    try:
        x = int(data['x'])
        y = int(data['y'])
        width = int(data.get('width', 1))
        height = int(data.get('height', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid position values'}), 400
    
    # Negative Werte nicht erlauben
    if x < 0 or y < 0 or width < 1 or height < 1:
        return jsonify({'error': 'Position values must be positive'}), 400
    
    position_data = {
        'widget_id': widget_id,
        'x': x,
        'y': y,
        'width': width,
        'height': height,
        'zone_id': data.get('zone_id', 'global'),
        'snap_to_grid': data.get('snap_to_grid', True),
        'last_update': datetime.utcnow().isoformat(),
        'history': data.get('history', [])  # Für Undo/Redo
    }
    
    with positions_lock:
        widget_positions_store[widget_id] = position_data
        save_positions_to_file()
    
    # WebSocket-Benachrichtigung
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('widget_position_update', {
            'widget_id': widget_id,
            'position': position_data
        })
    
    return jsonify({
        'success': True,
        'widget_id': widget_id,
        'position': position_data,
        'timestamp': datetime.utcnow().isoformat()
    })


@widget_positions_bp.route('/<widget_id>', methods=['GET'])
def get_widget_position(widget_id):
    """
    Position eines spezifischen Widgets abrufen
    """
    with positions_lock:
        position = widget_positions_store.get(widget_id)
    
    if not position:
        return jsonify({'error': 'Widget position not found'}), 404
    
    return jsonify({
        'widget_id': widget_id,
        'position': position
    })


@widget_positions_bp.route('/<widget_id>', methods=['DELETE'])
def delete_widget_position(widget_id):
    """
    Position eines Widgets löschen
    """
    with positions_lock:
        if widget_id not in widget_positions_store:
            return jsonify({'error': 'Widget position not found'}), 404
        
        del widget_positions_store[widget_id]
        save_positions_to_file()
    
    # WebSocket-Benachrichtigung
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('widget_position_deleted', {
            'widget_id': widget_id
        })
    
    return jsonify({
        'success': True,
        'widget_id': widget_id,
        'timestamp': datetime.utcnow().isoformat()
    })


@widget_positions_bp.route('/bulk', methods=['POST'])
def save_bulk_positions():
    """
    Mehrere Widget-Positionen auf einmal speichern
    Erwartet: { "positions": [{ "widget_id": "...", "x": 0, "y": 0, ...}, ...] }
    """
    data = request.get_json()
    
    if not data or 'positions' not in data:
        return jsonify({'error': 'No positions provided'}), 400
    
    positions = data['positions']
    saved_count = 0
    errors = []
    
    with positions_lock:
        for pos_data in positions:
            try:
                widget_id = pos_data.get('widget_id')
                if not widget_id:
                    errors.append({'widget_id': 'unknown', 'error': 'Missing widget_id'})
                    continue
                
                x = int(pos_data.get('x', 0))
                y = int(pos_data.get('y', 0))
                width = int(pos_data.get('width', 1))
                height = int(pos_data.get('height', 1))
                
                if x < 0 or y < 0 or width < 1 or height < 1:
                    errors.append({'widget_id': widget_id, 'error': 'Invalid position values'})
                    continue
                
                widget_positions_store[widget_id] = {
                    'widget_id': widget_id,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'zone_id': pos_data.get('zone_id', 'global'),
                    'snap_to_grid': pos_data.get('snap_to_grid', True),
                    'last_update': datetime.utcnow().isoformat(),
                    'history': pos_data.get('history', [])
                }
                saved_count += 1
                
            except Exception as e:
                errors.append({'widget_id': pos_data.get('widget_id', 'unknown'), 'error': str(e)})
        
        save_positions_to_file()
    
    return jsonify({
        'success': True,
        'saved_count': saved_count,
        'errors': errors,
        'total_positions': len(widget_positions_store),
        'timestamp': datetime.utcnow().isoformat()
    })


@widget_positions_bp.route('/<widget_id>/history', methods=['POST'])
def add_position_history(widget_id):
    """
    Position-History für Undo/Redo hinzufügen
    Erwartet: { "x": 0, "y": 0, "width": 1, "height": 1 }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    with positions_lock:
        if widget_id not in widget_positions_store:
            return jsonify({'error': 'Widget position not found'}), 404
        
        # Aktuelle Position zur History hinzufügen
        current_pos = widget_positions_store[widget_id]
        history_entry = {
            'x': current_pos['x'],
            'y': current_pos['y'],
            'width': current_pos.get('width', 1),
            'height': current_pos.get('height', 1),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # History auf max. 20 Einträge begrenzen
        if 'history' not in current_pos:
            current_pos['history'] = []
        
        current_pos['history'].append(history_entry)
        current_pos['history'] = current_pos['history'][-20:]
        
        widget_positions_store[widget_id] = current_pos
        save_positions_to_file()
    
    return jsonify({
        'success': True,
        'widget_id': widget_id,
        'history_length': len(current_pos['history']),
        'timestamp': datetime.utcnow().isoformat()
    })


@widget_positions_bp.route('/<widget_id>/undo', methods=['POST'])
def undo_position(widget_id):
    """
    Letzte Positionsänderung rückgängig machen
    """
    with positions_lock:
        if widget_id not in widget_positions_store:
            return jsonify({'error': 'Widget position not found'}), 404
        
        current_pos = widget_positions_store[widget_id]
        history = current_pos.get('history', [])
        
        if not history:
            return jsonify({'error': 'No history available'}), 404
        
        # Letzten History-Eintrag holen
        previous_pos = history.pop()
        
        # Aktuelle Position zur History (für Redo)
        current_pos['redo_stack'] = current_pos.get('redo_stack', [])
        current_pos['redo_stack'].append({
            'x': current_pos['x'],
            'y': current_pos['y'],
            'width': current_pos.get('width', 1),
            'height': current_pos.get('height', 1),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Position zurücksetzen
        current_pos['x'] = previous_pos['x']
        current_pos['y'] = previous_pos['y']
        current_pos['width'] = previous_pos.get('width', 1)
        current_pos['height'] = previous_pos.get('height', 1)
        current_pos['last_update'] = datetime.utcnow().isoformat()
        
        widget_positions_store[widget_id] = current_pos
        save_positions_to_file()
    
    # WebSocket-Benachrichtigung
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('widget_position_update', {
            'widget_id': widget_id,
            'position': current_pos,
            'action': 'undo'
        })
    
    return jsonify({
        'success': True,
        'widget_id': widget_id,
        'position': current_pos,
        'history_remaining': len(current_pos.get('history', [])),
        'timestamp': datetime.utcnow().isoformat()
    })


@widget_positions_bp.route('/<widget_id>/redo', methods=['POST'])
def redo_position(widget_id):
    """
    Rückgängig gemachte Änderung wiederherstellen
    """
    with positions_lock:
        if widget_id not in widget_positions_store:
            return jsonify({'error': 'Widget position not found'}), 404
        
        current_pos = widget_positions_store[widget_id]
        redo_stack = current_pos.get('redo_stack', [])
        
        if not redo_stack:
            return jsonify({'error': 'No redo available'}), 404
        
        # Letzten Redo-Eintrag holen
        next_pos = redo_stack.pop()
        
        # Aktuelle Position zur History
        if 'history' not in current_pos:
            current_pos['history'] = []
        current_pos['history'].append({
            'x': current_pos['x'],
            'y': current_pos['y'],
            'width': current_pos.get('width', 1),
            'height': current_pos.get('height', 1),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Position wiederherstellen
        current_pos['x'] = next_pos['x']
        current_pos['y'] = next_pos['y']
        current_pos['width'] = next_pos.get('width', 1)
        current_pos['height'] = next_pos.get('height', 1)
        current_pos['last_update'] = datetime.utcnow().isoformat()
        
        widget_positions_store[widget_id] = current_pos
        save_positions_to_file()
    
    # WebSocket-Benachrichtigung
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('widget_position_update', {
            'widget_id': widget_id,
            'position': current_pos,
            'action': 'redo'
        })
    
    return jsonify({
        'success': True,
        'widget_id': widget_id,
        'position': current_pos,
        'redo_remaining': len(current_pos.get('redo_stack', [])),
        'timestamp': datetime.utcnow().isoformat()
    })


@widget_positions_bp.route('/reset', methods=['POST'])
def reset_all_positions():
    """
    Alle Widget-Positionen zurücksetzen
    """
    with positions_lock:
        widget_positions_store.clear()
        save_positions_to_file()
    
    # WebSocket-Benachrichtigung
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('widget_positions_reset', {})
    
    return jsonify({
        'success': True,
        'message': 'All widget positions reset',
        'timestamp': datetime.utcnow().isoformat()
    })


# Initiale Positionen beim Modul-Import laden
load_positions_from_file()
