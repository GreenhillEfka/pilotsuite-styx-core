"""
Zone Summary Widget - Zone-based monitoring with live Home Assistant data
Flask Blueprint with REST API and WebSocket live updates
"""
from flask import Blueprint, jsonify, render_template, request
from flask_socketio import emit
from datetime import datetime, timedelta
import random
import threading
import time

# Create blueprint
zone_summary_bp = Blueprint('zone_summary', __name__, url_prefix='/widget/zone_summary')

# Zone configuration - aligned with HA habitus_zones (habitus/area names)
# Maps: zone_id (habitus zone type) -> HA area slug
ZONE_CONFIG = {
    'wohnbereich': {
        'name': 'Wohnzimmer',
        'icon': 'sofa',
        'entities': {
            'temperature': 'sensor.wohnbereich_temperature',
            'humidity': 'sensor.wohnbereich_humidity',
            'light': 'light.wohnbereich_main',
            'motion': 'binary_sensor.wohnbereich_motion',
            'window': 'binary_sensor.wohnbereich_window'
        },
        'thresholds': {
            'temp_min': 18,
            'temp_max': 26,
            'humidity_min': 30,
            'humidity_max': 70
        }
    },
    'schlafzimmer': {
        'name': 'Schlafzimmer',
        'icon': 'bed',
        'entities': {
            'temperature': 'sensor.schlafzimmer_temperature',
            'humidity': 'sensor.schlafzimmer_humidity',
            'light': 'light.schlafzimmer_main',
            'motion': 'binary_sensor.schlafzimmer_motion',
            'window': 'binary_sensor.schlafzimmer_window'
        },
        'thresholds': {
            'temp_min': 16,
            'temp_max': 24,
            'humidity_min': 30,
            'humidity_max': 65
        }
    },
    'kueche': {
        'name': 'Küche',
        'icon': 'chef-hat',
        'entities': {
            'temperature': 'sensor.kueche_temperature',
            'humidity': 'sensor.kueche_humidity',
            'light': 'light.kueche_main',
            'motion': 'binary_sensor.kueche_motion',
            'window': 'binary_sensor.kueche_window'
        },
        'thresholds': {
            'temp_min': 18,
            'temp_max': 28,
            'humidity_min': 30,
            'humidity_max': 70
        }
    },
    'badezimmer': {
        'name': 'Badezimmer',
        'icon': 'shower',
        'entities': {
            'temperature': 'sensor.badezimmer_temperature',
            'humidity': 'sensor.badezimmer_humidity',
            'light': 'light.badezimmer_main',
            'motion': 'binary_sensor.badezimmer_motion',
            'window': 'binary_sensor.badezimmer_window'
        },
        'thresholds': {
            'temp_min': 20,
            'temp_max': 28,
            'humidity_min': 40,
            'humidity_max': 80
        }
    },
    'kinderzimmer': {
        'name': 'Kinderzimmer',
        'icon': 'baby-face-outline',
        'entities': {
            'temperature': 'sensor.kinderzimmer_temperature',
            'humidity': 'sensor.kinderzimmer_humidity',
            'light': 'light.kinderzimmer_main',
            'motion': 'binary_sensor.kinderzimmer_motion',
            'window': 'binary_sensor.kinderzimmer_window'
        },
        'thresholds': {
            'temp_min': 18,
            'temp_max': 25,
            'humidity_min': 30,
            'humidity_max': 65
        }
    },
    'buero': {
        'name': 'Büro',
        'icon': 'desk',
        'entities': {
            'temperature': 'sensor.buero_temperature',
            'humidity': 'sensor.buero_humidity',
            'light': 'light.buero_main',
            'motion': 'binary_sensor.buero_motion',
            'window': 'binary_sensor.buero_window'
        },
        'thresholds': {
            'temp_min': 19,
            'temp_max': 25,
            'humidity_min': 35,
            'humidity_max': 65
        }
    },
    'aussenbereich': {
        'name': 'Außenbereich',
        'icon': 'tree',
        'entities': {
            'temperature': 'sensor.aussenbereich_temperature',
            'humidity': 'sensor.aussenbereich_humidity',
            'light': 'light.aussenbereich_main',
            'motion': 'binary_sensor.aussenbereich_motion',
            'window': None
        },
        'thresholds': {
            'temp_min': -10,
            'temp_max': 40,
            'humidity_min': 20,
            'humidity_max': 100
        }
    }
}

# In-memory store for zone data and history
zone_data_store = {}
zone_history_store = {}

def initialize_zone_stores():
    """Initialize zone data stores with default values"""
    for zone_id, config in ZONE_CONFIG.items():
        zone_data_store[zone_id] = {
            'name': config['name'],
            'icon': config['icon'],
            'presence': 'unknown',       # occupied / absent / unknown
            'media_playing': False,      # media player active in zone
            'lights_on': False,          # any light in zone on
            'temperature': 21.0,
            'humidity': 45.0,
            'light_state': 'off',
            'light_brightness': 0,
            'motion': False,
            'window_open': False,
            'presence_hold': 'auto',     # auto | force_on | force_off
            'alerts': [],
            'last_updated': datetime.now().isoformat()
        }

        # Initialize 24h history (288 points = 5 min intervals)
        zone_history_store[zone_id] = {
            'temperature': [],
            'humidity': []
        }

        # Pre-populate with simulated history
        now = datetime.now()
        for i in range(288):
            timestamp = now - timedelta(minutes=5 * (288 - i))
            base_temp = 20 + 3 * (0.5 + 0.5 * (i / 288))  # Daily cycle
            base_humidity = 45 + 10 * (0.5 - 0.5 * (i / 288))

            zone_history_store[zone_id]['temperature'].append({
                'timestamp': timestamp.isoformat(),
                'value': round(base_temp + random.uniform(-0.5, 0.5), 1)
            })
            zone_history_store[zone_id]['humidity'].append({
                'timestamp': timestamp.isoformat(),
                'value': round(base_humidity + random.uniform(-2, 2), 1)
            })

def get_zone_alerts(zone_id, data, config):
    """Determine alerts for a zone based on thresholds"""
    alerts = []
    thresholds = config.get('thresholds', {})

    # Temperature alerts
    temp = data.get('temperature', 20)
    temp_min = thresholds.get('temp_min', 18)
    temp_max = thresholds.get('temp_max', 26)

    if temp < temp_min:
        alerts.append({
            'type': 'warning',
            'icon': 'thermometer-low',
            'message': f'Temperatur zu niedrig ({temp}°C)'
        })
    elif temp > temp_max:
        alerts.append({
            'type': 'danger',
            'icon': 'thermometer-high',
            'message': f'Temperatur zu hoch ({temp}°C)'
        })

    # Humidity alerts
    humidity = data.get('humidity', 45)
    humidity_min = thresholds.get('humidity_min', 30)
    humidity_max = thresholds.get('humidity_max', 70)

    if humidity < humidity_min:
        alerts.append({
            'type': 'warning',
            'icon': 'water-percent-off',
            'message': f'Luftfeuchtigkeit zu niedrig ({humidity}%)'
        })
    elif humidity > humidity_max:
        alerts.append({
            'type': 'warning',
            'icon': 'water-percent',
            'message': f'Luftfeuchtigkeit zu hoch ({humidity}%)'
        })

    # Window open alert
    if data.get('window_open', False):
        alerts.append({
            'type': 'info',
            'icon': 'window-open',
            'message': 'Fenster ist offen'
        })

    return alerts

def simulate_zone_data():
    """Simulate realistic zone sensor data"""
    for zone_id, config in ZONE_CONFIG.items():
        current = zone_data_store.get(zone_id, {})

        # Temperature with slight variation
        base_temp = 21.0 if zone_id != 'outdoor' else 15.0
        temp = current.get('temperature', base_temp) + random.uniform(-0.3, 0.3)
        temp = max(10, min(35, temp))  # Clamp

        # Humidity with slight variation
        base_humidity = 45.0 if zone_id != 'outdoor' else 60.0
        humidity = current.get('humidity', base_humidity) + random.uniform(-2, 2)
        humidity = max(20, min(90, humidity))  # Clamp

        # Light state (random on/off with bias)
        light_on = random.random() > 0.6
        brightness = random.randint(40, 100) if light_on else 0

        # Presence (simulate occupancy — 40% occupied by default)
        presence = 'occupied' if random.random() > 0.6 else 'absent'

        # Media playing (10% chance when occupied)
        media_playing = presence == 'occupied' and random.random() > 0.9

        # Lights on derived from light_state
        lights_on = light_on

        # Motion (mostly off, occasional on)
        motion = random.random() > 0.8

        # Presence hold (mostly auto, 5% force_on, 5% force_off for simulation)
        hold_roll = random.random()
        presence_hold = 'auto' if hold_roll > 0.1 else ('force_on' if hold_roll > 0.05 else 'force_off')

        # Window (mostly closed)
        window_open = random.random() > 0.9

        # Update store
        zone_data_store[zone_id] = {
            'name': config['name'],
            'icon': config['icon'],
            'presence': presence,
            'media_playing': media_playing,
            'lights_on': lights_on,
            'temperature': round(temp, 1),
            'humidity': round(humidity, 1),
            'light_state': 'on' if light_on else 'off',
            'light_brightness': brightness,
            'motion': motion,
            'window_open': window_open,
            'presence_hold': presence_hold,
            'alerts': [],
            'last_updated': datetime.now().isoformat()
        }

        # Calculate alerts
        zone_data_store[zone_id]['alerts'] = get_zone_alerts(zone_id, zone_data_store[zone_id], config)

        # Update history (keep last 288 points = 24h at 5min intervals)
        zone_history_store[zone_id]['temperature'].append({
            'timestamp': datetime.now().isoformat(),
            'value': zone_data_store[zone_id]['temperature']
        })
        zone_history_store[zone_id]['humidity'].append({
            'timestamp': datetime.now().isoformat(),
            'value': zone_data_store[zone_id]['humidity']
        })

        # Trim history to 288 points
        if len(zone_history_store[zone_id]['temperature']) > 288:
            zone_history_store[zone_id]['temperature'].pop(0)
            zone_history_store[zone_id]['humidity'].pop(0)

def get_all_zones():
    """Get current data for all zones"""
    return {
        'zones': zone_data_store,
        'history': zone_history_store,
        'timestamp': datetime.now().isoformat(),
        'count': len(zone_data_store)
    }

def get_zone_detail(zone_id):
    """Get detailed data for a specific zone"""
    if zone_id not in ZONE_CONFIG:
        return None

    return {
        'id': zone_id,
        'config': ZONE_CONFIG[zone_id],
        'current': zone_data_store.get(zone_id, {}),
        'history': zone_history_store.get(zone_id, {}),
        'timestamp': datetime.now().isoformat()
    }

@zone_summary_bp.route('/')
def widget_view():
    """Render zone summary widget"""
    return render_template('widgets/zone_summary.html')

@zone_summary_bp.route('/api')
def api_zones():
    """REST API endpoint for all zone data"""
    return jsonify(get_all_zones())

@zone_summary_bp.route('/api/<zone_id>')
def api_zone_detail(zone_id):
    """REST API endpoint for specific zone"""
    data = get_zone_detail(zone_id)
    if not data:
        return jsonify({'error': 'Zone not found'}), 404
    return jsonify(data)

@zone_summary_bp.route('/api/config')
def api_config():
    """REST API endpoint for zone configuration"""
    return jsonify({
        'zones': list(ZONE_CONFIG.keys()),
        'config': ZONE_CONFIG
    })

def register_socketio_events(socketio):
    """Register WebSocket events for zone summary"""

    @socketio.on('connect', namespace='/zone_summary')
    def handle_connect():
        emit('connected', {'message': 'Connected to Zone Summary widget'})
        emit('zone_data', get_all_zones())

    @socketio.on('disconnect', namespace='/zone_summary')
    def handle_disconnect():
        print('Client disconnected from Zone Summary widget')

    @socketio.on('request_zones', namespace='/zone_summary')
    def handle_request_zones():
        emit('zone_data', get_all_zones())

    @socketio.on('request_zone', namespace='/zone_summary')
    def handle_request_zone(data):
        zone_id = data.get('zone_id')
        if zone_id:
            zone_data = get_zone_detail(zone_id)
            emit('zone_update', zone_data)

    @socketio.on('subscribe_zone', namespace='/zone_summary')
    def handle_subscribe(data):
        zone_id = data.get('zone_id')
        if zone_id:
            emit('subscribed', {
                'zone_id': zone_id,
                'message': f'Subscribed to zone {zone_id}'
            })

    @socketio.on('light_control', namespace='/zone_summary')
    def handle_light_control(data):
        """Handle light on/off requests"""
        zone_id = data.get('zone_id')
        action = data.get('action')  # 'on' or 'off'
        brightness = data.get('brightness', 100)

        if zone_id and zone_id in zone_data_store:
            # In production, this would call Home Assistant API
            zone_data_store[zone_id]['light_state'] = action
            zone_data_store[zone_id]['light_brightness'] = brightness if action == 'on' else 0
            zone_data_store[zone_id]['last_updated'] = datetime.now().isoformat()

            # Broadcast update
            emit('zone_update', {
                'zoneId': zone_id,
                'data': zone_data_store[zone_id]
            }, broadcast=True)

            emit('light_control_result', {
                'success': True,
                'zone_id': zone_id,
                'action': action,
                'brightness': brightness
            })

    @socketio.on('scene_activate', namespace='/zone_summary')
    def handle_scene_activate(data):
        """Handle scene activation requests"""
        zone_id = data.get('zone_id')
        scene = data.get('scene')

        if zone_id and scene:
            # In production, this would call Home Assistant API
            emit('scene_result', {
                'success': True,
                'zone_id': zone_id,
                'scene': scene,
                'message': f'Scene {scene} activated in {zone_id}'
            }, broadcast=True)

def broadcast_updates(socketio):
    """Broadcast zone updates (call periodically, e.g., every 5s)"""
    socketio.emit('zone_data', get_all_zones(), namespace='/zone_summary')

def start_zone_simulation(socketio):
    """Start background thread for simulating zone data updates"""
    def simulation_loop():
        while True:
            try:
                simulate_zone_data()
                broadcast_updates(socketio)
                time.sleep(5)  # Update every 5 seconds
            except Exception as e:
                print(f"Zone simulation error: {e}")
                time.sleep(1)

    thread = threading.Thread(target=simulation_loop, daemon=True)
    thread.start()
    return thread

# Initialize stores on module load
initialize_zone_stores()
