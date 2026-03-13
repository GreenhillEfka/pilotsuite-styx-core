"""Shared test fixtures for CoPilot Core tests.

Central fixture hub for all test suites (unit, integration, e2e).
Provides test clients, authentication, database connections, and cleanup.
"""
import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Global Fixtures (Auto-applied)
# =============================================================================

@pytest.fixture(autouse=True)
def reset_all_before_test():
    """Reset all global registries before each test.

    This ensures complete isolation between tests, especially when
    different test modules create their own Flask apps and register
    blueprints independently.

    Runs automatically before EVERY test (autouse=True).
    """
    _reset_all_registries()
    yield
    # Optional cleanup after test
    _reset_all_registries()


@pytest.fixture(autouse=True)
def disable_auth_for_tests(monkeypatch):
    """Disable authentication in test environment.

    Tests run without /data/options.json, so auth_required defaults to True
    and get_auth_token returns empty — causing all requests to get 401.
    Setting COPILOT_AUTH_REQUIRED=false allows tests to run without auth.
    """
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")


@pytest.fixture(autouse=True)
def reset_auth_token_cache():
    """Reset the auth token cache before each test.

    Prevents token state leaking between test modules — the cache is a
    module-level variable with a 60s TTL, so a test that sets it will
    poison all subsequent tests that create a Flask test client.
    """
    try:
        import copilot_core.api.security as sec
        sec._token_cache = ("", 0.0)
    except ImportError:
        pass
    yield
    # Also reset after the test
    try:
        import copilot_core.api.security as sec
        sec._token_cache = ("", 0.0)
    except ImportError:
        pass


@pytest.fixture
def isolated_blueprint_test():
    """Fixture for tests that need isolated blueprint registries.

    Use this fixture when your test creates its own Flask app instance
    and registers blueprints directly (not importing from main.py).

    This fixture resets all global blueprint registries before AND after
    the test to ensure complete isolation.

    Example:
        def test_my_blueprint(isolated_blueprint_test):
            app = Flask(__name__)
            app.register_blueprint(my_bp)
            # ... test code ...

    NOT needed for tests that import from main.py (e.g., test_tag_api.py),
    as those share the main app instance and should NOT reset registries.
    """
    _reset_all_registries()
    yield
    _reset_all_registries()


def _reset_all_registries():
    """Helper to reset all known global registries.

    Used by isolated_blueprint_test fixture to ensure test isolation.
    """
    # Tags API
    try:
        import copilot_core.tags.api as tags_api
        tags_api._registry = None
    except (ImportError, AttributeError):
        pass

    # Candidates API
    try:
        import copilot_core.candidates.api as candidates_api
        candidates_api._candidate_store = None
    except (ImportError, AttributeError):
        pass

    # Automations API
    try:
        import copilot_core.automations.api as automations_api
        automations_api._engine = None
    except (ImportError, AttributeError):
        pass

    # Regional API
    try:
        import copilot_core.regional.api as regional_api
        regional_api._provider = None
        regional_api._warning_manager = None
        regional_api._fuel_tracker = None
        regional_api._tariff_engine = None
        regional_api._alert_engine = None
        regional_api._forecast_engine = None
        regional_api._battery_optimizer = None
        regional_api._heat_pump_controller = None
        regional_api._ev_charging_planner = None
        regional_api._gas_meter = None
    except (ImportError, AttributeError):
        pass

    # UniFi API
    try:
        import copilot_core.unifi.api as unifi_api
        unifi_api._unifi_service = None
    except (ImportError, AttributeError):
        pass

    # System Health API
    try:
        import copilot_core.system_health.api as health_api
        health_api._service = None
    except (ImportError, AttributeError):
        pass

    # Zone Editor API - reset zone engine
    try:
        from copilot_core.api.v1.zone_editor import reset_zone_engine
        reset_zone_engine()
    except (ImportError, AttributeError):
        pass

    # Prediction API
    try:
        import copilot_core.prediction.api as pred_api
        pred_api._forecaster = None
        pred_api._optimizer = None
        pred_api._ts_forecaster = None
        pred_api._load_scheduler = None
        pred_api._schedule_planner = None
        pred_api._weather_optimizer = None
    except (ImportError, AttributeError):
        pass

    # Energy API
    try:
        import copilot_core.energy.api as energy_api
        energy_api._energy_service = None
        energy_api._cost_tracker = None
        energy_api._fingerprinter = None
        energy_api._report_generator = None
        energy_api._demand_response = None
    except (ImportError, AttributeError):
        pass

    # Energy init
    try:
        import copilot_core.energy as energy_mod
        energy_mod._energy_service = None
    except (ImportError, AttributeError):
        pass

    # Event Processor
    try:
        import copilot_core.ingest.event_processor as ep
        ep._processor = None
    except (ImportError, AttributeError):
        pass

    # Agent Config
    try:
        import copilot_core.agent_config as ac
        ac._config = None
        ac._llm_provider = None
        ac._conversation_module = None
        ac._start_time = None
    except (ImportError, AttributeError):
        pass

    # User Preferences
    try:
        import copilot_core.storage.user_preferences as up
        up._store = None
    except (ImportError, AttributeError):
        pass

    # Core init
    try:
        import copilot_core as core
        core._system_health_service = None
        core._unifi_service = None
    except (ImportError, AttributeError):
        pass

    # Phase 5: Sharing API (Cross-Home Sync)
    try:
        import copilot_core.sharing.api as sharing_api
        sharing_api._sync_service = None
        sharing_api._registry = None
        sharing_api._discovery = None
    except (ImportError, AttributeError):
        pass

    # Phase 5: Collective Intelligence API (Federated Learning)
    try:
        import copilot_core.collective_intelligence.api as fed_api
        fed_api._service = None
    except (ImportError, AttributeError):
        pass

    # Conversation API (LLM Provider)
    try:
        import copilot_core.api.v1.conversation as conv_api
        conv_api._llm_provider = None
        conv_api._mcp_tools = None
    except (ImportError, AttributeError):
        pass

    # Zone Editor API
    try:
        import copilot_core.api.v1.zone_editor as zone_api
        zone_api._zone_engine = None
    except (ImportError, AttributeError):
        pass

    # MCP REST API - reset connections
    try:
        import copilot_core.api.v1.mcp as mcp_api
        mcp_api._MCP_CONNECTIONS.clear()
    except (ImportError, AttributeError):
        pass


# =============================================================================
# Test Client Fixtures
# =============================================================================

@pytest.fixture(scope='session')
def app_config():
    """Application configuration for tests."""
    return {
        'TESTING': True,
        'DEBUG': True,
        'SECRET_KEY': 'test-secret-key-for-testing',
        'NEO4J_URI': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        'NEO4J_USER': os.getenv('NEO4J_USER', 'neo4j'),
        'NEO4J_PASSWORD': os.getenv('NEO4J_PASSWORD', 'testpassword123'),
        'LLM_PROVIDER': 'mock',
        'CACHE_ENABLED': False,
        'RATE_LIMIT_ENABLED': False,
    }


@pytest.fixture(scope='function')
def test_app(app_config):
    """Create Flask app instance for testing.
    
    Uses function scope to ensure each test gets a fresh app instance
    with properly initialized blueprints and services.
    """
    from copilot_core.app import create_app
    app = create_app()
    app.config.update(app_config)
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def test_client(test_app):
    """Create test client for API requests."""
    with test_app.test_client() as client:
        yield client


@pytest.fixture
def test_app_context(test_app):
    """Provide application context for tests."""
    with test_app.app_context():
        yield test_app


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture
def valid_auth_token():
    """Provide valid authentication token for tests."""
    # In real tests, this would be generated by the auth system
    # For integration tests, we use a mock token
    return 'test_token_' + datetime.now().strftime('%Y%m%d%H%M%S')


@pytest.fixture
def auth_headers(valid_auth_token):
    """Provide authentication headers for requests."""
    return {
        'Authorization': f'Bearer {valid_auth_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def admin_auth_token():
    """Provide admin-level authentication token."""
    return 'admin_token_' + datetime.now().strftime('%Y%m%d%H%M%S')


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def neo4j_driver(app_config):
    """Create Neo4j driver instance for tests."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            app_config['NEO4J_URI'],
            auth=(app_config['NEO4J_USER'], app_config['NEO4J_PASSWORD'])
        )
        yield driver
        driver.close()
    except ImportError:
        pytest.skip("Neo4j not installed")


@pytest.fixture
def clean_database(neo4j_driver):
    """Clean database before and after test."""
    # Clean before
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    
    yield
    
    # Clean after
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


# =============================================================================
# WebSocket Fixtures
# =============================================================================

@pytest.fixture
def websocket_client(test_app):
    """Create WebSocket client for testing."""
    class MockWebSocketClient:
        def __init__(self, app):
            self.app = app
            self.connection = None
        
        def connect(self, path, headers=None):
            self.connection = MockWebSocketConnection(path, headers)
            return self.connection
        
        def disconnect(self):
            if self.connection:
                self.connection.close()
    
    class MockWebSocketConnection:
        def __init__(self, path, headers):
            self.path = path
            self.headers = headers
            self.messages = []
        
        def send(self, message):
            self.messages.append(message)
        
        def receive(self, timeout=5.0):
            # Mock response
            return {'type': 'mock', 'data': {}}
        
        def close(self):
            pass
    
    yield MockWebSocketClient(test_app)


# =============================================================================
# Data Fixtures
# =============================================================================

@pytest.fixture
def sample_zone_data():
    """Sample zone data for tests."""
    return {
        'name': 'Test Zone',
        'rooms': ['living_room', 'kitchen'],
        'config': {
            'target_temperature': 22.0,
            'target_humidity': 50
        }
    }


@pytest.fixture
def sample_automation_data():
    """Sample automation data for tests."""
    return {
        'name': 'Test Automation',
        'trigger': {
            'type': 'time',
            'time': '08:00'
        },
        'actions': [
            {
                'type': 'light',
                'entity_id': 'light.living_room',
                'state': 'on'
            }
        ],
        'enabled': True
    }


@pytest.fixture
def sample_event_data():
    """Sample event data for tests."""
    return {
        'type': 'temperature_reading',
        'source': 'sensor.living_room',
        'data': {
            'temperature': 22.5,
            'humidity': 45.0
        }
    }


@pytest.fixture
def sample_notification_data():
    """Sample notification data for tests."""
    return {
        'title': 'Test Notification',
        'message': 'This is a test',
        'priority': 'normal',
        'channel': 'push'
    }


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider for tests."""
    mock_provider = Mock()
    mock_provider.chat.return_value = {
        'response': 'Mock response',
        'tokens_used': 10
    }
    mock_provider.stream.return_value = iter(['chunk1', 'chunk2'])
    return mock_provider


@pytest.fixture
def mock_homeassistant():
    """Create mock Home Assistant client for tests."""
    mock_ha = Mock()
    mock_ha.get_states.return_value = []
    mock_ha.call_service.return_value = {'success': True}
    mock_ha.get_entities.return_value = []
    return mock_ha


@pytest.fixture
def mock_neo4j_session():
    """Create mock Neo4j session for tests."""
    mock_session = Mock()
    mock_session.run.return_value = Mock()
    mock_session.__enter__ = Mock(return_value=mock_session)
    mock_session.__exit__ = Mock(return_value=False)
    return mock_session


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def freeze_time():
    """Freeze time for deterministic tests."""
    from freezegun import freeze_time as ft
    with ft('2026-03-01 12:00:00') as frozen:
        yield frozen


@pytest.fixture(scope='session')
def test_run_id():
    """Generate unique test run ID."""
    return f'test_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}'


@pytest.fixture
def temp_file(tmp_path):
    """Create temporary file for tests."""
    file_path = tmp_path / 'test_file.txt'
    file_path.write_text('test content')
    yield file_path
    file_path.unlink(missing_ok=True)


# =============================================================================
# Integration Test Specific Fixtures
# =============================================================================

@pytest.fixture
def integration_test_config():
    """Configuration specific to integration tests."""
    return {
        'TEST_MODE': 'integration',
        'EXTERNAL_SERVICES_ENABLED': True,
        'DATABASE_CLEANUP': True,
        'MOCK_EXTERNAL_APIS': False,
    }


@pytest.fixture
def seeded_database(clean_database, neo4j_driver):
    """Database with seed data for integration tests."""
    with neo4j_driver.session() as session:
        # Seed basic data
        session.run("""
            CREATE (n:Zone {name: 'Test Zone', id: 'test-zone-1'})
            CREATE (n:Sensor {name: 'Test Sensor', id: 'test-sensor-1'})
        """)
    yield
    # Cleanup happens in clean_database fixture


@pytest.fixture
def parallel_test_worker():
    """Fixture for parallel test execution with pytest-xdist."""
    import os
    worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'master')
    return worker_id
