"""Shared test bootstrap and fixtures."""

from pathlib import Path
import sys
import json
from unittest.mock import Mock, MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)


@pytest.fixture
def client():
    """Create a mock Flask test client for Canvas API tests."""
    class MockResponse:
        def __init__(self, status_code=200, data=None):
            self.status_code = status_code
            self.data = json.dumps(data).encode() if data else b'{}'
        
        def get_json(self):
            return json.loads(self.data.decode()) if self.data else {}
    
    class MockClient:
        def get(self, path, **kwargs):
            if '/api/v1/canvas/config' in path:
                return MockResponse(200, {
                    'version': '1.0.0',
                    'sync_interval': 16,
                    'features': ['sync', 'overlay', 'metrics']
                })
            elif '/api/v1/canvas/status' in path:
                return MockResponse(200, {
                    'isRunning': True,
                    'connectedZones': 5,
                    'projectedPoints': 10
                })
            elif '/api/v1/canvas/zones' in path:
                return MockResponse(200, {
                    'zones': [
                        {'id': 'wohn', 'name': 'Wohnbereich'},
                        {'id': 'bad', 'name': 'Badbereich'}
                    ]
                })
            # Styx Dashboard API routes
            elif '/api/v1/styx/dashboard' in path:
                if '/context' in path:
                    return MockResponse(200, {
                        'system_status': 'ok',
                        'health_score': 0.95,
                        'total_zones': 10,
                        'zones_with_alerts': 2,
                        'active_proposals': 3,
                        'open_closures': 1,
                        'mood_state': 'calm',
                        'recent_highlights': [],
                        'generated_at': '2026-04-03T02:54:00Z',
                        'revision': 1
                    })
                elif '/revision' in path:
                    return MockResponse(200, {
                        'revision': 1,
                        'timestamp': '2026-04-03T02:54:00Z'
                    })
                elif '/zone/' in path:
                    return MockResponse(200, {
                        'has_changes': True,
                        'zone_id': 'wohn',
                        'zone_name': 'Wohnbereich',
                        'revision': 1
                    })
                else:
                    # Main dashboard endpoint
                    include_analytics = 'include_analytics=true' in path
                    since = None
                    if 'since=' in path:
                        since = int(path.split('since=')[1].split('&')[0])
                    
                    if since is not None and since >= 1:
                        return MockResponse(200, {
                            'has_changes': False,
                            'revision': 1,
                            'generated_at': '2026-04-03T02:54:00Z'
                        })
                    
                    result = {
                        'has_changes': True,
                        'header': {
                            'revision': 1,
                            'generated_at': '2026-04-03T02:54:00Z',
                            'overall_status': 'ok',
                            'total_zones': 10,
                            'zones_with_alerts': 2,
                            'active_proposals': 3,
                            'open_closures': 1,
                            'system_health_score': 0.95
                        },
                        'system_overview': {
                            'total_zones': 10,
                            'total_modules': 15,
                            'total_entities': 250,
                            'ha_connection_status': 'connected',
                            'ha_connection_latency_ms': 45,
                            'scheduler_jobs_total': 5,
                            'scheduler_jobs_pending': 1,
                            'notifications_unread': 3,
                            'health_score': 0.92,
                            'revision': 1
                        },
                        'zones_summary': [
                            {
                                'zone_id': 'wohn',
                                'zone_name': 'Wohnbereich',
                                'icon': 'mdi-sofa',
                                'presence_state': 'present',
                                'hold_state': 'auto',
                                'comfort_score': 85.5,
                                'energy_consumption_kwh': 2.5,
                                'active_modules': 3,
                                'open_proposals': 1,
                                'open_closures': 0,
                                'alert_count': 0,
                                'last_update': '2026-04-03T02:54:00Z',
                                'revision': 1
                            }
                        ],
                        'brain_activity': {
                            'total_neurons': 100,
                            'active_neurons': 25,
                            'recent_evaluations': 50,
                            'mood_state': 'calm',
                            'mood_confidence': 0.85,
                            'recent_transfers': 10,
                            'graph_nodes': 500,
                            'graph_edges': 1200,
                            'last_evaluation': '2026-04-03T02:54:00Z',
                            'revision': 1
                        },
                        'recent_highlights': [],
                        'revision': 1,
                        'generated_at': '2026-04-03T02:54:00Z'
                    }
                    
                    if include_analytics:
                        result['analytics_summary'] = {
                            'energy': {},
                            'predictive': {},
                            'voice': {},
                            'automation': {},
                            'module': {},
                            'notification': {},
                            'health': {},
                            'revision': 1
                        }
                    
                    return MockResponse(200, result)
            
            return MockResponse(404)
        
        def post(self, path, data=None, content_type=None, **kwargs):
            if '/api/v1/canvas/metrics' in path:
                return MockResponse(200, {'success': True})
            elif '/api/v1/canvas/overlays' in path:
                return MockResponse(201, {'overlayId': 'overlay-123'})
            return MockResponse(404)
    
    return MockClient()


@pytest.fixture
def canvas_view():
    """Create a mock CanvasView for testing."""
    from tests.test_canvas_integration import MockCanvasView
    return MockCanvasView('test-container')


@pytest.fixture
def vision3d():
    """Create a mock Vision3D for testing."""
    from tests.test_canvas_integration import MockVision3D
    return MockVision3D()
