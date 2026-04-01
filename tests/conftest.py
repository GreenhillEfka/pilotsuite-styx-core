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
