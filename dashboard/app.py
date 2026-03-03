"""
PilotSuite Styx Dashboard - Flask Application
Main dashboard server running on port 8766
Optimized for WebSocket performance with batch updates and compression
"""
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_compress import Compress
from config import config
import os
import threading
import time
import json
import gzip
from collections import defaultdict
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(config['default'])
app.config['COMPRESSION_MIMETYPES'] = ['application/json', 'text/javascript', 'application/javascript']
app.config['COMPRESS_LEVEL'] = 6

# Initialize Compress for GZIP
Compress(app)

# Initialize SocketIO with performance optimizations
# async_mode='gevent' for better concurrency, ping_interval for connection health
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_interval=25,
    ping_timeout=10,
    max_http_buffer_size=1e6,
    json=json
)

# Performance tracking
performance_metrics = {
    'start_time': time.time(),
    'messages_sent': 0,
    'messages_received': 0,
    'total_latency_ms': 0,
    'batch_updates_sent': 0,
    'clients_connected': 0,
    'compression_ratio': 0.0,
    'last_update': None
}

# Batch update queue for 500ms batching
update_queue = defaultdict(list)
update_lock = threading.Lock()
BATCH_INTERVAL_MS = 500

# Import widget blueprints
from widgets.system_status import system_status_bp, register_socketio_events as register_system_status_events, broadcast_updates as broadcast_system_status
from widgets.brain_graph import brain_graph_bp, register_socketio_events as register_brain_graph_events
from widgets.chat_widget import chat_widget_bp, register_socketio_events as register_chat_events
from widgets.sensor_overview import sensor_overview_bp, register_socketio_events as register_sensor_events, broadcast_updates as broadcast_sensor_status
from widgets.zone_summary import zone_summary_bp, register_socketio_events as register_zone_summary_events, broadcast_updates as broadcast_zone_status, start_zone_simulation
from widgets.optimization import performance_tracker, get_all_metrics as get_widget_performance_metrics
from api.v1.performance import performance_bp, update_websocket_metrics, track_performance
from api.v1.dashboard import dashboard_bp
from api.v1.widget_positions import widget_positions_bp

# Register widget blueprints
app.register_blueprint(system_status_bp)
app.register_blueprint(brain_graph_bp)
app.register_blueprint(chat_widget_bp)
app.register_blueprint(sensor_overview_bp)
app.register_blueprint(zone_summary_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(widget_positions_bp)

# Register widget Socket.IO events
register_system_status_events(socketio)
register_brain_graph_events(socketio)
register_chat_events(socketio, app.config)
register_sensor_events(socketio)
register_zone_summary_events(socketio)

# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard_habitus():
    """Habitus Dashboard mit 10 Tabs"""
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    """Get dashboard status"""
    return jsonify({
        'status': 'running',
        'version': '13.0.3',
        'port': app.config['PORT'],
        'rag_api': app.config['RAG_API_URL'],
        'widgets': ['system_status', 'brain_graph', 'chat', 'sensor_overview'],
        'optimizations': ['batch_updates', 'client_debouncing', 'gzip_compression']
    })

@app.route('/api/overview')
def get_overview():
    """Get overview data"""
    return jsonify({
        'system_status': 'online',
        'active_services': 3,
        'pending_tasks': 0
    })

@app.route('/api/v1/performance')
def get_performance():
    """Get dashboard performance metrics"""
    uptime = time.time() - performance_metrics['start_time']
    avg_latency = (performance_metrics['total_latency_ms'] / 
                   max(1, performance_metrics['messages_sent']))
    
    return jsonify({
        'uptime_seconds': uptime,
        'clients_connected': performance_metrics['clients_connected'],
        'messages_sent': performance_metrics['messages_sent'],
        'messages_received': performance_metrics['messages_received'],
        'batch_updates_sent': performance_metrics['batch_updates_sent'],
        'avg_latency_ms': round(avg_latency, 2),
        'compression_ratio': performance_metrics['compression_ratio'],
        'last_update': performance_metrics['last_update'],
        'target_latency_ms': 100,
        'current_status': 'optimal' if avg_latency < 100 else 'degraded'
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection with performance tracking"""
    performance_metrics['clients_connected'] += 1
    update_websocket_metrics(connections=performance_metrics['clients_connected'])
    print(f'Client connected (total: {performance_metrics["clients_connected"]})')
    emit('connected', {
        'message': 'Connected to PilotSuite Styx Dashboard',
        'performance': {
            'batch_interval_ms': BATCH_INTERVAL_MS,
            'compression': 'gzip',
            'target_latency_ms': 100
        }
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    performance_metrics['clients_connected'] = max(0, performance_metrics['clients_connected'] - 1)
    update_websocket_metrics(connections=performance_metrics['clients_connected'])
    print(f'Client disconnected (total: {performance_metrics["clients_connected"]})')

@socketio.on('request_update')
def handle_request_update(data):
    """Handle update requests from clients"""
    start_time = time.time()
    emit('update', {
        'type': 'status',
        'data': {'status': 'updated'}
    })
    latency_ms = (time.time() - start_time) * 1000
    performance_metrics['total_latency_ms'] += latency_ms
    performance_metrics['messages_sent'] += 1

@socketio.on('performance_ping')
def handle_performance_ping(data):
    """Handle performance ping from client for latency measurement"""
    start_time = time.time()
    client_timestamp = data.get('timestamp', time.time())
    emit('performance_pong', {
        'client_timestamp': client_timestamp,
        'server_timestamp': time.time(),
        'latency_ms': (time.time() - start_time) * 1000
    })
    performance_metrics['messages_received'] += 1
    performance_metrics['messages_sent'] += 1

@socketio.on('request_zone_data')
def handle_request_zone_data(data):
    """Handle zone data requests from dashboard client"""
    zones = data.get('zones', [])
    print(f'[Dashboard] Zone data requested for: {zones}')
    
    # Return current zone data from store
    from api.v1.dashboard import zone_data_store, DEFAULT_ZONES_CONFIG
    
    for zone_id in zones:
        zone_data = zone_data_store.get(zone_id, {})
        emit('zone_update', {
            'zoneId': zone_id,
            'data': zone_data
        })

@socketio.on('ha_discovery_complete')
def handle_ha_discovery_complete(data):
    """Handle HA discovery completion notification"""
    print('[Dashboard] HA Discovery complete notification received')
    # Broadcast to all connected clients
    emit('ha_discovery_complete', {'status': 'complete'}, broadcast=True)

def queue_update(namespace, event_type, data):
    """Queue an update for batched broadcasting (500ms interval)"""
    with update_lock:
        update_queue[namespace].append({
            'event': event_type,
            'data': data,
            'timestamp': time.time()
        })

def flush_batched_updates():
    """Flush all queued updates in a single batch"""
    global update_queue
    
    with update_lock:
        if not any(update_queue.values()):
            return
        
        start_time = time.time()
        batches_sent = 0
        total_payload_size = 0
        total_compressed_size = 0
        
        for namespace, updates in list(update_queue.items()):
            if not updates:
                continue
            
            # Combine all updates for this namespace into one message
            batch_data = {
                'batch': True,
                'count': len(updates),
                'updates': updates,
                'timestamp': time.time()
            }
            
            # Serialize payload
            payload = json.dumps(batch_data)
            total_payload_size += len(payload.encode('utf-8'))
            
            # Compress if payload is large (>1KB)
            if len(payload) > 1024:
                compressed = gzip.compress(payload.encode('utf-8'))
                compression_ratio = len(compressed) / len(payload)
                performance_metrics['compression_ratio'] = compression_ratio
                total_compressed_size += len(compressed)
                socketio.emit('batch_update', batch_data, namespace=namespace if namespace != '/' else None)
            else:
                socketio.emit('batch_update', batch_data, namespace=namespace if namespace != '/' else None)
            
            batches_sent += 1
            performance_metrics['messages_sent'] += 1
            
            # Track widget performance
            for update in updates:
                widget_name = namespace.strip('/') if namespace != '/' else 'dashboard'
                performance_tracker.record_update(
                    widget_name,
                    (time.time() - start_time) * 1000,
                    len(payload.encode('utf-8'))
                )
        
        # Update global metrics
        update_websocket_metrics(
            connections=performance_metrics['clients_connected'],
            messages_sent=batches_sent,
            batch_updates=batches_sent,
            compression_savings=total_payload_size - total_compressed_size
        )
        
        performance_metrics['batch_updates_sent'] += batches_sent
        performance_metrics['last_update'] = datetime.now().isoformat()
        
        # Clear the queue
        update_queue.clear()
        
        latency_ms = (time.time() - start_time) * 1000
        performance_metrics['total_latency_ms'] += latency_ms

def broadcast_loop():
    """Background thread to broadcast live updates with batching (500ms intervals)"""
    while True:
        try:
            # Collect updates from all widgets
            start_time = time.time()
            
            # Get system status and queue for batching
            from widgets.system_status import get_system_metrics
            system_metrics = get_system_metrics()
            queue_update('/system_status', 'metrics', system_metrics)
            
            # Get sensor data and queue for batching
            from widgets.sensor_overview import get_all_sensors
            sensor_data = get_all_sensors()
            queue_update('/sensor_overview', 'sensor_data', sensor_data)
            
            # Flush batched updates (every 500ms)
            flush_batched_updates()
            
            # Sleep for batch interval
            time.sleep(BATCH_INTERVAL_MS / 1000.0)
            
        except Exception as e:
            print(f"Broadcast error: {e}")
            time.sleep(1)  # Back off on error

def start_dashboard():
    """Start the dashboard server"""
    print(f"Starting PilotSuite Styx Dashboard on port {app.config['PORT']}")
    
    # Start background broadcast thread
    broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True)
    broadcast_thread.start()
    print("Live update broadcast started")
    
    # Start zone simulation (5s updates for zone cards)
    zone_simulation_thread = start_zone_simulation(socketio)
    print("Zone simulation started (5s updates)")
    
    socketio.run(
        app,
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG_MODE']
    )

if __name__ == '__main__':
    start_dashboard()
