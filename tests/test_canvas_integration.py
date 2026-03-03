"""Tests for Canvas/View Integration in PilotSuite Dashboard.

Tests CanvasView functionality including:
- Canvas initialization and setup
- Vision3D connectivity
- Overlay positioning and rendering
- Zone synchronization
- Event handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import json


# ── Mock Three.js Objects ─────────────────────────────────────────────────

class MockVector3:
    """Mock THREE.Vector3"""
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z
    
    def clone(self):
        return MockVector3(self.x, self.y, self.z)
    
    def copy(self, other):
        self.x = other.x
        self.y = other.y
        self.z = other.z
        return self
    
    def project(self, camera):
        # Return normalized projection
        return MockVector3(
            (self.x / 50) * 0.5,
            (self.y / 50) * 0.5,
            self.z / 100
        )


class MockMesh:
    """Mock THREE.Mesh"""
    def __init__(self, name="zone-test"):
        self.name = name
        self.userData = {
            'type': 'zone',
            'id': name,
            'name': f'Zone {name}'
        }
        self.position = MockVector3()
        self.scale = MockVector3(1, 1, 1)
        self.visible = True
        
    def getWorldPosition(self, target):
        target.x = self.position.x
        target.y = self.position.y
        target.z = self.position.z
        return target


class MockCamera:
    """Mock THREE.Camera"""
    def __init__(self):
        self.position = MockVector3(30, 25, 30)


class MockVision3D:
    """Mock Vision3D for CanvasView testing"""
    def __init__(self):
        self.camera = MockCamera()
        self.zoneMeshes = {}
        self.zoneData = {}
        self._event_handlers = {}
        
    def on(self, event_name, callback):
        """Register event handler"""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(callback)
    
    def trigger_event(self, event_name, data):
        """Trigger event for testing"""
        if event_name in self._event_handlers:
            for handler in self._event_handlers[event_name]:
                handler(data)


# ── Mock DOM Elements ─────────────────────────────────────────────────────

class MockCanvas:
    """Mock HTMLCanvasElement"""
    def __init__(self):
        self.width = 800
        self.height = 600
        self.style = MockCSSStyle()
        self._context = MockCanvasContext()
        self.parentNode = None
        
    def getContext(self, context_type):
        if context_type == '2d':
            return self._context
        return None


class MockCanvasContext:
    """Mock CanvasRenderingContext2D"""
    def __init__(self):
        self.clearRect_calls = []
        self.beginPath_calls = []
        self.arc_calls = []
        self.fill_calls = []
        self.stroke_calls = []
        self.fillStyle = '#000000'
        self.strokeStyle = '#000000'
        self.lineWidth = 1
        self.lineDash = []
        
    def clearRect(self, x, y, w, h):
        self.clearRect_calls.append((x, y, w, h))
    
    def beginPath(self):
        self.beginPath_calls.append(True)
    
    def arc(self, x, y, radius, start, end):
        self.arc_calls.append((x, y, radius, start, end))
    
    def fill(self):
        self.fill_calls.append(True)
    
    def stroke(self):
        self.stroke_calls.append(True)
    
    def moveTo(self, x, y):
        pass
    
    def lineTo(self, x, y):
        pass
    
    def setLineDash(self, dash):
        self.lineDash = dash
    
    def createRadialGradient(self, x1, y1, r1, x2, y2, r2):
        return MockGradient()


class MockGradient:
    """Mock CanvasGradient"""
    def addColorStop(self, offset, color):
        pass


class MockCSSStyle:
    """Mock CSSStyleDeclaration"""
    def __init__(self):
        self.cssText = ''
        self.width = ''
        self.height = ''
        self.display = ''
        self.position = ''
        self.top = ''
        self.left = ''
        self.opacity = ''
        self.zIndex = ''
        self.pointerEvents = ''


class MockElement:
    """Mock HTMLElement"""
    def __init__(self, tag_name='div'):
        self.tagName = tag_name
        self.style = MockCSSStyle()
        self.className = ''
        self.dataset = {}
        self._children = []
        self._event_listeners = {}
        self._rect = {
            'width': 800,
            'height': 600,
            'left': 0,
            'top': 0
        }
        
    def appendChild(self, child):
        self._children.append(child)
        child.parentNode = self
        return child
    
    def removeChild(self, child):
        if child in self._children:
            self._children.remove(child)
        return child
    
    def querySelector(self, selector):
        """Mock querySelector"""
        if '.' in selector:
            class_name = selector.replace('.', '')
            for child in self._children:
                if hasattr(child, 'className') and class_name in child.className:
                    return child
        return None
    
    def getBoundingClientRect(self):
        return self._rect
    
    def addEventListener(self, event, handler, options=None):
        if event not in self._event_listeners:
            self._event_listeners[event] = []
        self._event_listeners[event].append(handler)
    
    def removeEventListener(self, event, handler):
        if event in self._event_listeners and handler in self._event_listeners[event]:
            self._event_listeners[event].remove(handler)


class MockContainer(MockElement):
    """Mock container element"""
    def __init__(self, container_id='test-container'):
        super().__init__('div')
        self.id = container_id
        self.style.position = 'relative'


class MockDocument:
    """Mock document object"""
    def __init__(self):
        self._elements = {}
        self._created_elements = []
        self._dispatched_events = []
        
    def getElementById(self, element_id):
        return self._elements.get(element_id)
    
    def createElement(self, tag_name):
        element = MockElement(tag_name)
        if tag_name == 'canvas':
            element = MockCanvas()
        self._created_elements.append(element)
        return element
    
    def addEventListener(self, event, handler, options=None):
        pass
    
    def dispatchEvent(self, event):
        self._dispatched_events.append(event)
    
    def registerElement(self, element_id, element):
        element.id = element_id
        self._elements[element_id] = element


class MockWindow:
    """Mock window object"""
    def __init__(self):
        self._event_listeners = {}
        self.devicePixelRatio = 2
        
    def addEventListener(self, event, handler, options=None):
        if event not in self._event_listeners:
            self._event_listeners[event] = []
        self._event_listeners[event].append(handler)
    
    def requestAnimationFrame(self, callback):
        return 1


class MockCustomEvent:
    """Mock CustomEvent"""
    def __init__(self, event_name, options=None):
        self.type = event_name
        self.detail = options.get('detail') if options else None


# ── CanvasView Implementation (Python mock) ──────────────────────────────

class CanvasView:
    """Python implementation of CanvasView for testing"""
    
    def __init__(self, container_id, options=None):
        self.containerId = container_id
        self.options = options or {}
        self.options.setdefault('syncInterval', 16)
        self.options.setdefault('showOverlays', True)
        self.options.setdefault('interactive', True)
        
        self.canvas = None
        self.ctx = None
        self.overlayLayer = None
        self.vision3d = None
        self.projectedPoints = {}
        self.overlays = {}
        self.isRunning = False
        
        self._mock_document = MockDocument()
        self._mock_window = MockWindow()
        
        self.init()
    
    def init(self):
        """Initialize CanvasView"""
        self.container = self._mock_document.getElementById(self.containerId)
        if not self.container:
            raise ValueError(f'Container not found: {self.containerId}')
        
        self.setupCanvas()
        self.setupOverlayLayer()
        self.setupEventListeners()
    
    def setupCanvas(self):
        """Setup canvas element"""
        self.canvas = self._mock_document.createElement('canvas')
        self.canvas.className = 'canvas-view-layer'
        self.canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10;'
        self.container.appendChild(self.canvas)
        self.ctx = self.canvas.getContext('2d')
        self.resize()
    
    def setupOverlayLayer(self):
        """Setup overlay div"""
        self.overlayLayer = self._mock_document.createElement('div')
        self.overlayLayer.className = 'canvas-overlay-layer'
        self.overlayLayer.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:20;'
        self.container.appendChild(self.overlayLayer)
    
    def setupEventListeners(self):
        """Setup event listeners"""
        pass  # Mocked
    
    def connectToVision3D(self, vision3d_instance):
        """Connect to Vision3D instance"""
        self.vision3d = vision3d_instance
        self.vision3d.on('zoneHover', self.onZoneHover)
        self.vision3d.on('zoneSelect', self.onZoneSelect)
        self.startSync()
    
    def startSync(self):
        """Start synchronization loop"""
        self.isRunning = True
    
    def stopSync(self):
        """Stop synchronization loop"""
        self.isRunning = False
    
    def syncWith3D(self):
        """Synchronize with 3D view"""
        if not self.vision3d:
            return
        
        self.ctx.clearRect(0, 0, self.canvas.width, self.canvas.height)
        self.updateProjectedPoints()
        self.updateOverlays()
        self.draw()
    
    def updateProjectedPoints(self):
        """Update projected 3D points to 2D canvas"""
        if not self.vision3d or not self.vision3d.camera:
            return
        
        self.projectedPoints = {}
        
        for zone_id, mesh in self.vision3d.zoneMeshes.items():
            if zone_id.endswith('-indicator'):
                continue
            
            world_position = MockVector3(
                mesh.position.x,
                mesh.position.y,
                mesh.position.z
            )
            projected = world_position.clone().project(self.vision3d.camera)
            
            x = (projected.x * 0.5 + 0.5) * self.canvas.width
            y = (-projected.y * 0.5 + 0.5) * self.canvas.height
            
            self.projectedPoints[zone_id] = {
                'x': x,
                'y': y,
                'visible': projected.z < 1,
                'worldPosition': world_position,
                'data': mesh.userData
            }
    
    def updateOverlays(self):
        """Update overlay positions"""
        for zone_id, point in self.projectedPoints.items():
            if not point['visible']:
                if zone_id in self.overlays:
                    self.overlays[zone_id].style.display = 'none'
                continue
            
            if zone_id not in self.overlays:
                self.createOverlay(zone_id, point)
            else:
                self.positionOverlay(self.overlays[zone_id], point)
    
    def createOverlay(self, zone_id, point):
        """Create new overlay element"""
        overlay = self._mock_document.createElement('div')
        overlay.className = 'canvas-view-overlay'
        overlay.dataset['zoneId'] = zone_id
        overlay.innerHTML = f'<div class="overlay-title">{point["data"].get("name", zone_id)}</div>'
        
        self.overlayLayer.appendChild(overlay)
        self.overlays[zone_id] = overlay
        self.positionOverlay(overlay, point)
    
    def positionOverlay(self, overlay, point):
        """Position overlay at projected point"""
        rect_width = 150  # Mock width
        x = point['x'] - rect_width / 2
        y = point['y'] - 40  # Mock height
        
        overlay.style.left = f'{x}px'
        overlay.style.top = f'{y}px'
        overlay.style.display = 'block'
        overlay.style.opacity = str(max(0.3, 1 - point.get('z', 0) * 0.3))
    
    def draw(self):
        """Draw canvas elements"""
        self.drawZoneConnections()
        self.drawActiveRegions()
        self.drawProjectedPoints()
    
    def drawZoneConnections(self):
        """Draw connections between zones"""
        points = [p for p in self.projectedPoints.values() if p['visible']]
        
        self.ctx.strokeStyle = 'rgba(59, 130, 246, 0.3)'
        self.ctx.lineWidth = 1
        self.ctx.setLineDash([5, 5])
        
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                dx = points[i]['x'] - points[j]['x']
                dy = points[i]['y'] - points[j]['y']
                dist = (dx ** 2 + dy ** 2) ** 0.5
                
                if dist < 150:
                    self.ctx.beginPath()
                    self.ctx.moveTo(points[i]['x'], points[i]['y'])
                    self.ctx.lineTo(points[j]['x'], points[j]['y'])
                    self.ctx.stroke()
        
        self.ctx.setLineDash([])
    
    def drawActiveRegions(self):
        """Draw active regions around zones"""
        for zone_id, point in self.projectedPoints.items():
            if not point['visible']:
                continue
            
            zone_data = self.vision3d.zoneData.get(zone_id) if self.vision3d else None
            if zone_data:
                activity = zone_data.get('activity', 0)
                if activity > 0.5:
                    radius = 30 + activity * 20
                    gradient = self.ctx.createRadialGradient(
                        point['x'], point['y'], 0,
                        point['x'], point['y'], radius
                    )
                    gradient.addColorStop(0, f'rgba(34, 197, 94, {activity * 0.3})')
                    gradient.addColorStop(1, 'rgba(34, 197, 94, 0)')
                    
                    self.ctx.fillStyle = gradient
                    self.ctx.beginPath()
                    self.ctx.arc(point['x'], point['y'], radius, 0, 3.14159 * 2)
                    self.ctx.fill()
    
    def drawProjectedPoints(self):
        """Draw projected zone points"""
        for point in self.projectedPoints.values():
            if not point['visible']:
                continue
            
            self.ctx.fillStyle = '#22c55e'
            self.ctx.beginPath()
            self.ctx.arc(point['x'], point['y'], 6, 0, 3.14159 * 2)
            self.ctx.fill()
    
    def onZoneHover(self, data):
        """Handle zone hover event"""
        overlay = self.overlays.get(data.get('id'))
        if overlay:
            overlay.className = overlay.className + ' hovered'
    
    def onZoneSelect(self, data):
        """Handle zone select event"""
        overlay = self.overlays.get(data.get('id'))
        if overlay:
            overlay.style.display = 'block'
            overlay.className = overlay.className + ' selected'
    
    def resize(self):
        """Resize canvas to container"""
        rect = self.container.getBoundingClientRect()
        self.canvas.width = rect['width']
        self.canvas.height = rect['height']
    
    def dispose(self):
        """Cleanup and dispose"""
        self.stopSync()
        self.overlays.clear()


# ── Helper function to create CanvasView with registered container ──────

def create_canvas_view(container_id, options=None, mock_doc=None):
    """Create CanvasView with container registration"""
    doc = mock_doc if mock_doc else MockDocument()
    container = MockContainer(container_id)
    doc.registerElement(container_id, container)
    
    view = CanvasView.__new__(CanvasView)
    view.containerId = container_id
    view.options = options or {}
    view.options.setdefault('syncInterval', 16)
    view.options.setdefault('showOverlays', True)
    view.options.setdefault('interactive', True)
    
    view.canvas = None
    view.ctx = None
    view.overlayLayer = None
    view.vision3d = None
    view.projectedPoints = {}
    view.overlays = {}
    view.isRunning = False
    
    view._mock_document = doc
    view._mock_window = MockWindow()
    view.container = container
    
    view.setupCanvas()
    view.setupOverlayLayer()
    view.setupEventListeners()
    
    return view


# ── Test Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_container():
    """Create mock container element"""
    container = MockContainer('test-container')
    return container


@pytest.fixture
def mock_vision3d():
    """Create mock Vision3D instance"""
    return MockVision3D()


@pytest.fixture
def mock_document():
    """Create mock document"""
    return MockDocument()


# ── Test Cases ──────────────────────────────────────────────────────────────

class TestCanvasViewInitialization:
    """Tests for CanvasView initialization"""
    
    def test_container_required(self):
        """Test that CanvasView requires a container"""
        with pytest.raises(ValueError):
            CanvasView('nonexistent')
    
    def test_default_options(self, mock_document):
        """Test default options are set correctly"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        assert view.options['syncInterval'] == 16
        assert view.options['showOverlays'] is True
        assert view.options['interactive'] is True
    
    def test_custom_options(self, mock_document):
        """Test custom options are applied"""
        view = create_canvas_view('test-container', {
            'syncInterval': 32,
            'showOverlays': False
        }, mock_doc=mock_document)
        
        assert view.options['syncInterval'] == 32
        assert view.options['showOverlays'] is False
    
    def test_canvas_element_created(self, mock_document):
        """Test canvas element is created"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        assert view.canvas is not None
        assert 'canvas-view-layer' in view.canvas.className
    
    def test_overlay_layer_created(self, mock_document):
        """Test overlay layer is created"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        assert view.overlayLayer is not None
        assert 'canvas-overlay-layer' in view.overlayLayer.className
    
    def test_canvas_resized_to_container(self, mock_document):
        """Test canvas is resized to container dimensions"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        assert view.canvas.width == 800
        assert view.canvas.height == 600


class TestVision3DConnection:
    """Tests for Vision3D connectivity"""
    
    def test_connect_to_vision3d(self, mock_document, mock_vision3d):
        """Test connecting to Vision3D instance"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        view.connectToVision3D(mock_vision3d)
        
        assert view.vision3d is mock_vision3d
        assert view.isRunning is True
    
    def test_event_handlers_registered(self, mock_document, mock_vision3d):
        """Test event handlers are registered"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        view.connectToVision3D(mock_vision3d)
        
        assert 'zoneHover' in mock_vision3d._event_handlers
        assert 'zoneSelect' in mock_vision3d._event_handlers
    
    def test_zone_hover_callback(self, mock_document, mock_vision3d):
        """Test zone hover callback"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Create overlay
        view.overlays['zone-1'] = MockElement('div')
        
        # Trigger hover event
        mock_vision3d.trigger_event('zoneHover', {'id': 'zone-1'})
        
        assert 'hovered' in view.overlays['zone-1'].className
    
    def test_zone_select_callback(self, mock_document, mock_vision3d):
        """Test zone select callback"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Create overlay
        view.overlays['zone-1'] = MockElement('div')
        view.overlays['zone-1'].style.display = 'none'
        
        # Trigger select event
        mock_vision3d.trigger_event('zoneSelect', {'id': 'zone-1'})
        
        assert view.overlays['zone-1'].style.display == 'block'
        assert 'selected' in view.overlays['zone-1'].className


class TestProjectedPoints:
    """Tests for point projection"""
    
    def test_projected_points_calculated(self, mock_document, mock_vision3d):
        """Test 3D points are projected to 2D"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Add zone mesh
        mesh = MockMesh('wohn')
        mock_vision3d.zoneMeshes['wohn'] = mesh
        
        view.updateProjectedPoints()
        
        assert 'wohn' in view.projectedPoints
        assert 'x' in view.projectedPoints['wohn']
        assert 'y' in view.projectedPoints['wohn']
    
    def test_indicators_skipped(self, mock_document, mock_vision3d):
        """Test indicator meshes are skipped"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Add indicator mesh
        mesh = MockMesh('wohn-indicator')
        mock_vision3d.zoneMeshes['wohn-indicator'] = mesh
        
        view.updateProjectedPoints()
        
        assert 'wohn-indicator' not in view.projectedPoints
    
    def test_projection_visibility(self, mock_document, mock_vision3d):
        """Test projection visibility based on depth"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Add zone mesh
        mesh = MockMesh('wohn')
        mock_vision3d.zoneMeshes['wohn'] = mesh
        
        view.updateProjectedPoints()
        
        assert 'visible' in view.projectedPoints['wohn']


class TestOverlayManagement:
    """Tests for overlay management"""
    
    def test_overlay_created_for_visible_zone(self, mock_document, mock_vision3d):
        """Test overlay is created for visible zone"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Set up projection
        view.projectedPoints = {
            'zone-1': {
                'x': 400,
                'y': 300,
                'visible': True,
                'data': {'name': 'Wohnbereich'}
            }
        }
        
        view.updateOverlays()
        
        assert 'zone-1' in view.overlays
        assert 'canvas-view-overlay' in view.overlays['zone-1'].className
    
    def test_overlay_hidden_for_invisible_zone(self, mock_document, mock_vision3d):
        """Test overlay is hidden for invisible zone"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Create existing overlay
        overlay = MockElement('div')
        overlay.style.display = 'block'
        view.overlays['zone-1'] = overlay
        
        # Set projection as invisible
        view.projectedPoints = {
            'zone-1': {
                'x': 400,
                'y': 300,
                'visible': False,
                'data': {'name': 'Wohnbereich'}
            }
        }
        
        view.updateOverlays()
        
        assert overlay.style.display == 'none'
    
    def test_overlay_positioned_correctly(self, mock_document, mock_vision3d):
        """Test overlay is positioned at projected point"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Create overlay
        overlay = MockElement('div')
        # Set mock dimensions for getBoundingClientRect
        overlay._rect = {'width': 150, 'height': 80, 'left': 0, 'top': 0}
        point = {'x': 400, 'y': 300, 'z': 0.5}
        
        view.positionOverlay(overlay, point)
        
        # Allow for both int and float representations (JS produces floats)
        assert overlay.style.left in ['325px', '325.0px']
        assert overlay.style.top in ['260px', '260.0px']
        assert overlay.style.display == 'block'


class TestCanvasDrawing:
    """Tests for canvas drawing operations"""
    
    def test_clear_called_on_sync(self, mock_document, mock_vision3d):
        """Test canvas is cleared before drawing"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        view.syncWith3D()
        
        assert (0, 0, 800, 600) in view.ctx.clearRect_calls
    
    def test_points_drawn(self, mock_document, mock_vision3d):
        """Test projected points are drawn"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        view.projectedPoints = {
            'zone-1': {'x': 400, 'y': 300, 'visible': True, 'data': {}}
        }
        
        view.drawProjectedPoints()
        
        assert len(view.ctx.arc_calls) > 0
        assert view.ctx.fill_calls
    
    def test_active_regions_drawn(self, mock_document, mock_vision3d):
        """Test active regions are drawn for active zones"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        view.projectedPoints = {
            'zone-1': {'x': 400, 'y': 300, 'visible': True, 'data': {}}
        }
        mock_vision3d.zoneData['zone-1'] = {'activity': 0.8}
        
        view.drawActiveRegions()
        
        # Should create radial gradient and draw arc
        assert view.ctx.beginPath_calls
    
    def test_connections_drawn(self, mock_document, mock_vision3d):
        """Test zone connections are drawn"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Add two nearby zones
        view.projectedPoints = {
            'zone-1': {'x': 400, 'y': 300, 'visible': True, 'data': {}},
            'zone-2': {'x': 450, 'y': 320, 'visible': True, 'data': {}}
        }
        
        # Track setLineDash calls to verify it was set during drawing
        original_setLineDash = view.ctx.setLineDash
        lineDash_history = []
        
        def tracked_setLineDash(dash):
            lineDash_history.append(dash.copy() if hasattr(dash, 'copy') else list(dash))
            original_setLineDash(dash)
        
        view.ctx.setLineDash = tracked_setLineDash
        
        view.drawZoneConnections()
        
        # Should have set line dash to [5, 5] during drawing, then reset to []
        assert [5, 5] in lineDash_history, f"Expected [5, 5] in lineDash history, got {lineDash_history}"
        assert view.ctx.lineDash == [], "Line dash should be reset to [] after drawing"


class TestSyncControl:
    """Tests for sync control"""
    
    def test_start_sync_sets_running(self, mock_document, mock_vision3d):
        """Test startSync sets isRunning to True"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.isRunning = False
        
        view.startSync()
        
        assert view.isRunning is True
    
    def test_stop_sync_clears_running(self, mock_document, mock_vision3d):
        """Test stopSync sets isRunning to False"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        view.stopSync()
        
        assert view.isRunning is False
    
    def test_sync_without_vision3d(self, mock_document):
        """Test sync does nothing without Vision3D"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        # Should not raise
        view.syncWith3D()
        
        assert view.vision3d is None


class TestCleanup:
    """Tests for cleanup and disposal"""
    
    def test_dispose_clears_overlays(self, mock_document, mock_vision3d):
        """Test dispose clears overlays"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        view.overlays['zone-1'] = MockElement('div')
        
        view.dispose()
        
        assert len(view.overlays) == 0
        assert view.isRunning is False
    
    def test_stop_sync_on_dispose(self, mock_document, mock_vision3d):
        """Test dispose stops sync"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        view.dispose()
        
        assert view.isRunning is False


class TestIntegration:
    """Integration tests for CanvasView"""
    
    def test_full_workflow(self, mock_document, mock_vision3d):
        """Test complete CanvasView workflow"""
        # Create CanvasView
        view = create_canvas_view('test-container', mock_doc=mock_document)
        
        # Verify initialization
        assert view.canvas is not None
        assert view.overlayLayer is not None
        
        # Connect to Vision3D
        view.connectToVision3D(mock_vision3d)
        assert view.isRunning is True
        
        # Add zones
        mock_vision3d.zoneMeshes['wohn'] = MockMesh('wohn')
        mock_vision3d.zoneMeshes['bad'] = MockMesh('bad')
        mock_vision3d.zoneData['wohn'] = {'activity': 0.8, 'alertCount': 1}
        
        # Sync
        view.syncWith3D()
        
        # Verify projections
        assert 'wohn' in view.projectedPoints
        assert 'bad' in view.projectedPoints
        
        # Verify overlays created
        assert 'wohn' in view.overlays
        assert 'bad' in view.overlays
        
        # Trigger zone select
        mock_vision3d.trigger_event('zoneSelect', {'id': 'wohn'})
        assert 'selected' in view.overlays['wohn'].className
        
        # Cleanup
        view.dispose()
        assert len(view.overlays) == 0
        assert view.isRunning is False
    
    def test_multiple_sync_cycles(self, mock_document, mock_vision3d):
        """Test multiple sync cycles"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        mock_vision3d.zoneMeshes['zone-1'] = MockMesh('zone-1')
        
        # Multiple syncs
        for _ in range(3):
            view.syncWith3D()
        
        # Canvas should be cleared each time
        assert len(view.ctx.clearRect_calls) == 3
    
    def test_vision3d_data_updates(self, mock_document, mock_vision3d):
        """Test handling of Vision3D data updates"""
        view = create_canvas_view('test-container', mock_doc=mock_document)
        view.connectToVision3D(mock_vision3d)
        
        # Initial data
        mock_vision3d.zoneMeshes['zone-1'] = MockMesh('zone-1')
        mock_vision3d.zoneData['zone-1'] = {'activity': 0.3}
        
        view.syncWith3D()
        
        # Update data
        mock_vision3d.zoneData['zone-1'] = {'activity': 0.9, 'alertCount': 2}
        
        view.syncWith3D()
        
        # Should handle updated data
        assert 'zone-1' in view.projectedPoints