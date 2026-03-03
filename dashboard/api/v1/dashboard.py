"""
PilotSuite Styx Dashboard API v1
Dashboard-Konfiguration und Habituszonen-Endpoints
"""
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import threading
import time

dashboard_bp = Blueprint('dashboard_v1', __name__, url_prefix='/api/v1/dashboard')

# In-Memory Storage für Zone-Daten (wird durch HA-Integration ersetzt)
zone_data_store = {}
zone_lock = threading.Lock()

# Standard-Konfiguration für Habituszonen
DEFAULT_ZONES_CONFIG = [
    {
        'id': 'wohn',
        'name': 'Wohnbereich',
        'icon': 'mdi-sofa',
        'enabled': True,
        'priority': 1,
        'entities': {
            'temperature': 'sensor.wohnzimmer_temperatur',
            'humidity': 'sensor.wohnzimmer_luftfeuchtigkeit',
            'lights': ['light.wohnzimmer_deckenlicht', 'light.wohnzimmer_stehlampe']
        }
    },
    {
        'id': 'bad',
        'name': 'Badbereich',
        'icon': 'mdi-shower',
        'enabled': True,
        'priority': 2,
        'entities': {
            'temperature': 'sensor.bad_temperatur',
            'humidity': 'sensor.bad_luftfeuchtigkeit',
            'lights': ['light.bad_deckenlicht']
        }
    },
    {
        'id': 'koch',
        'name': 'Kochbereich',
        'icon': 'mdi-stove',
        'enabled': True,
        'priority': 3,
        'entities': {
            'temperature': 'sensor.kuche_temperatur',
            'humidity': 'sensor.kuche_luftfeuchtigkeit',
            'lights': ['light.kuche_deckenlicht', 'light.kuche_arbeitsplatte']
        }
    },
    {
        'id': 'buero',
        'name': 'Bürobereich',
        'icon': 'mdi-desk',
        'enabled': True,
        'priority': 4,
        'entities': {
            'temperature': 'sensor.buro_temperatur',
            'humidity': 'sensor.buro_luftfeuchtigkeit',
            'lights': ['light.buro_schreibtisch', 'light.buro_deckenlicht']
        }
    },
    {
        'id': 'gang',
        'name': 'Gangbereich',
        'icon': 'mdi-door-open',
        'enabled': True,
        'priority': 5,
        'entities': {
            'temperature': 'sensor.gang_temperatur',
            'lights': ['light.gang_deckenlicht']
        }
    },
    {
        'id': 'schlaf',
        'name': 'Schlafbereich',
        'icon': 'mdi-bed',
        'enabled': True,
        'priority': 6,
        'entities': {
            'temperature': 'sensor.schlafzimmer_temperatur',
            'humidity': 'sensor.schlafzimmer_luftfeuchtigkeit',
            'lights': ['light.schlafzimmer_deckenlicht', 'light.schlafzimmer_nachttisch']
        }
    },
    {
        'id': 'mira',
        'name': 'Zimmer Mira',
        'icon': 'mdi-account-girl',
        'enabled': True,
        'priority': 7,
        'entities': {
            'temperature': 'sensor.zimmer_mira_temperatur',
            'lights': ['light.zimmer_mira_deckenlicht', 'light.zimmer_mira_schreibtisch']
        }
    },
    {
        'id': 'paul',
        'name': 'Zimmer Paul',
        'icon': 'mdi-account-boy',
        'enabled': True,
        'priority': 8,
        'entities': {
            'temperature': 'sensor.zimmer_paul_temperatur',
            'lights': ['light.zimmer_paul_deckenlicht', 'light.zimmer_paul_schreibtisch']
        }
    },
    {
        'id': 'terrasse',
        'name': 'Terrassenbereich',
        'icon': 'mdi-patio-grass',
        'enabled': True,
        'priority': 9,
        'entities': {
            'temperature': 'sensor.terrasse_temperatur',
            'lights': ['light.terrasse_deckenlicht', 'light.terrasse_stimmungslicht']
        }
    },
    {
        'id': 'aussen',
        'name': 'Aussenbereich',
        'icon': 'mdi-tree',
        'enabled': True,
        'priority': 10,
        'entities': {
            'temperature': 'sensor.garten_temperatur',
            'humidity': 'sensor.garten_luftfeuchtigkeit',
            'lights': ['light.garten_weg', 'light.garten_baum']
        }
    }
]


@dashboard_bp.route('/config', methods=['GET'])
def get_dashboard_config():
    """
    Dashboard-Konfiguration abrufen
    Enthält alle Habituszonen mit Metadaten
    """
    config = {
        'version': '13.0.3',
        'zones': DEFAULT_ZONES_CONFIG,
        'theme_support': ['light', 'dark'],
        'features': {
            'tabs': True,
            'websocket': True,
            'alerts': True,
            'responsive': True
        },
        'layout': {
            'tab_height': 56,
            'header_height': 64,
            'footer_height': 48
        }
    }
    return jsonify(config)


@dashboard_bp.route('/zones', methods=['GET'])
def get_zones():
    """
    Alle Habituszonen abrufen
    """
    zones = []
    with zone_lock:
        for zone_config in DEFAULT_ZONES_CONFIG:
            zone_id = zone_config['id']
            zone_data = zone_data_store.get(zone_id, {})
            
            zones.append({
                'id': zone_id,
                'name': zone_config['name'],
                'icon': zone_config['icon'],
                'enabled': zone_config['enabled'],
                'priority': zone_config['priority'],
                'data': zone_data,
                'alert_count': zone_data.get('alert_count', 0),
                'last_update': zone_data.get('last_update')
            })
    
    return jsonify({
        'zones': zones,
        'total': len(zones),
        'active_alerts': sum(z['alert_count'] for z in zones)
    })


@dashboard_bp.route('/zones/<zone_id>', methods=['GET'])
def get_zone(zone_id):
    """
    Daten einer spezifischen Habituszone abrufen
    """
    zone_config = next((z for z in DEFAULT_ZONES_CONFIG if z['id'] == zone_id), None)
    
    if not zone_config:
        return jsonify({'error': 'Zone not found'}), 404
    
    with zone_lock:
        zone_data = zone_data_store.get(zone_id, {})
    
    return jsonify({
        'id': zone_id,
        'name': zone_config['name'],
        'icon': zone_config['icon'],
        'enabled': zone_config['enabled'],
        'priority': zone_config['priority'],
        'entities': zone_config['entities'],
        'data': zone_data,
        'alert_count': zone_data.get('alert_count', 0),
        'last_update': zone_data.get('last_update')
    })


@dashboard_bp.route('/zones/<zone_id>/data', methods=['PUT'])
def update_zone_data(zone_id):
    """
    Daten einer Habituszone aktualisieren (für HA-Integration)
    """
    zone_config = next((z for z in DEFAULT_ZONES_CONFIG if z['id'] == zone_id), None)
    
    if not zone_config:
        return jsonify({'error': 'Zone not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    with zone_lock:
        zone_data_store[zone_id] = {
            **zone_data_store.get(zone_id, {}),
            **data,
            'last_update': datetime.utcnow().isoformat()
        }
    
    # WebSocket-Benachrichtigung auslösen
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('zone_update', {
            'zoneId': zone_id,
            'data': zone_data_store[zone_id]
        })
    
    return jsonify({
        'success': True,
        'zone_id': zone_id,
        'timestamp': datetime.utcnow().isoformat()
    })


@dashboard_bp.route('/zones/<zone_id>/alerts', methods=['GET'])
def get_zone_alerts(zone_id):
    """
    Alerts einer spezifischen Zone abrufen
    """
    zone_config = next((z for z in DEFAULT_ZONES_CONFIG if z['id'] == zone_id), None)
    
    if not zone_config:
        return jsonify({'error': 'Zone not found'}), 404
    
    with zone_lock:
        zone_data = zone_data_store.get(zone_id, {})
    
    alerts = zone_data.get('alerts', [])
    
    return jsonify({
        'zone_id': zone_id,
        'zone_name': zone_config['name'],
        'alert_count': len(alerts),
        'alerts': alerts
    })


@dashboard_bp.route('/zones/<zone_id>/alerts', methods=['POST'])
def add_zone_alert(zone_id):
    """
    Neuer Alert für eine Zone
    """
    zone_config = next((z for z in DEFAULT_ZONES_CONFIG if z['id'] == zone_id), None)
    
    if not zone_config:
        return jsonify({'error': 'Zone not found'}), 404
    
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message required'}), 400
    
    alert = {
        'id': f'alert_{zone_id}_{int(time.time())}',
        'message': data['message'],
        'severity': data.get('severity', 'info'),  # info, warning, error
        'timestamp': datetime.utcnow().isoformat(),
        'acknowledged': False
    }
    
    with zone_lock:
        if zone_id not in zone_data_store:
            zone_data_store[zone_id] = {}
        
        if 'alerts' not in zone_data_store[zone_id]:
            zone_data_store[zone_id]['alerts'] = []
        
        zone_data_store[zone_id]['alerts'].append(alert)
        zone_data_store[zone_id]['alert_count'] = len(zone_data_store[zone_id]['alerts'])
        zone_data_store[zone_id]['last_update'] = datetime.utcnow().isoformat()
    
    # WebSocket-Benachrichtigung
    if hasattr(current_app, 'socketio'):
        from flask_socketio import emit
        current_app.socketio.emit('alert_update', {
            'zoneId': zone_id,
            'alertCount': zone_data_store[zone_id]['alert_count'],
            'alert': alert
        })
    
    return jsonify({
        'success': True,
        'alert': alert,
        'timestamp': datetime.utcnow().isoformat()
    })


@dashboard_bp.route('/zones/<zone_id>/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(zone_id, alert_id):
    """
    Alert bestätigen
    """
    zone_config = next((z for z in DEFAULT_ZONES_CONFIG if z['id'] == zone_id), None)
    
    if not zone_config:
        return jsonify({'error': 'Zone not found'}), 404
    
    with zone_lock:
        zone_data = zone_data_store.get(zone_id, {})
        alerts = zone_data.get('alerts', [])
        
        for alert in alerts:
            if alert['id'] == alert_id:
                alert['acknowledged'] = True
                alert['acknowledged_at'] = datetime.utcnow().isoformat()
                break
        
        # Bestätigte Alerts entfernen
        zone_data['alerts'] = [a for a in alerts if not a.get('acknowledged', False)]
        zone_data['alert_count'] = len(zone_data['alerts'])
        zone_data_store[zone_id] = zone_data
    
    return jsonify({
        'success': True,
        'zone_id': zone_id,
        'alert_id': alert_id,
        'timestamp': datetime.utcnow().isoformat()
    })


@dashboard_bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    """
    Dashboard-Statistiken
    """
    with zone_lock:
        total_zones = len(DEFAULT_ZONES_CONFIG)
        enabled_zones = sum(1 for z in DEFAULT_ZONES_CONFIG if z['enabled'])
        total_alerts = sum(
            zone_data_store.get(z['id'], {}).get('alert_count', 0)
            for z in DEFAULT_ZONES_CONFIG
        )
        
        zones_with_data = sum(
            1 for z in DEFAULT_ZONES_CONFIG
            if zone_data_store.get(z['id'], {}).get('last_update')
        )
    
    return jsonify({
        'total_zones': total_zones,
        'enabled_zones': enabled_zones,
        'zones_with_data': zones_with_data,
        'total_alerts': total_alerts,
        'last_update': datetime.utcnow().isoformat()
    })


@dashboard_bp.route('/theme', methods=['GET', 'PUT'])
def theme_management():
    """
    Theme-Einstellungen verwalten
    """
    if request.method == 'GET':
        return jsonify({
            'themes': ['light', 'dark'],
            'default': 'light',
            'auto_detect': True
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        theme = data.get('theme')
        
        if theme not in ['light', 'dark']:
            return jsonify({'error': 'Invalid theme'}), 400
        
        # Theme wird client-seitig gespeichert, Server merkt sich nur Präferenz
        return jsonify({
            'success': True,
            'theme': theme,
            'timestamp': datetime.utcnow().isoformat()
        })


def initialize_zone_data():
    """
    Initiale Zonendaten setzen (für Demo-Zwecke)
    """
    for zone in DEFAULT_ZONES_CONFIG:
        zone_data_store[zone['id']] = {
            'temperature': 21.5,
            'humidity': 45,
            'lights': 2,
            'brightness': 60,
            'alert_count': 0,
            'alerts': [],
            'last_update': datetime.utcnow().isoformat()
        }


# Initiale Daten beim Modul-Import
initialize_zone_data()
