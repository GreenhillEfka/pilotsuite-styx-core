# Integration Test Suite

Comprehensive integration tests for PilotSuite Styx Core.

## Test Coverage

This suite includes **20+ integration tests** covering:

### API & Authentication
- `test_api_auth_integration.py` - Auth flows, token validation, security middleware
- `test_dashboard_api_integration.py` - Dashboard data, real-time updates, performance

### Core Systems
- `test_automation_engine_integration.py` - Automation lifecycle, triggers, execution
- `test_event_processing_integration.py` - Event ingestion, batch processing, streaming
- `test_neural_network_integration.py` - Neurons, brain graph, visualization

### Intelligence & Search
- `test_rag_search_integration.py` - Hybrid search, vector store, Searxng integration
- `test_llm_provider_integration.py` - LLM providers, fallback, load balancing

### Notifications & Zones
- `test_notification_system_integration.py` - Notifications, scheduling, preferences
- `test_zone_management_integration.py` - Zones, climate control, scheduling

### Infrastructure
- `test_mcp_server_integration.py` - MCP server, tools, resources
- `test_system_health_integration.py` - Health checks, metrics, alerting

## Running Tests

### All Integration Tests
```bash
cd copilot_core/rootfs/usr/src/app
pytest tests/integration/ -v
```

### With Coverage
```bash
pytest tests/integration/ --cov=copilot_core --cov-report=html
```

### Parallel Execution (4x faster)
```bash
pytest tests/integration/ -n auto
```

### Specific Test File
```bash
pytest tests/integration/test_api_auth_integration.py -v
```

### Specific Test Function
```bash
pytest tests/integration/test_api_auth_integration.py::TestAuthIntegration::test_auth_token_lifecycle -v
```

## Test Structure

Each test file follows this pattern:
- **Test Classes** - Group related tests (e.g., `TestAuthIntegration`)
- **Test Methods** - Individual test cases (e.g., `test_auth_token_lifecycle`)
- **Fixtures** - Shared setup/teardown from `conftest.py`

## Fixtures

Key fixtures from `tests/conftest.py`:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_client` | function | Flask test client |
| `valid_auth_token` | function | Valid auth token |
| `auth_headers` | function | Auth headers dict |
| `neo4j_driver` | session | Neo4j database driver |
| `clean_database` | function | Clean DB before/after |
| `websocket_client` | function | WebSocket test client |
| `mock_llm_provider` | function | Mock LLM provider |
| `mock_homeassistant` | function | Mock HA client |
| `sample_*_data` | function | Sample test data |

## Requirements

Install test dependencies:
```bash
pip install pytest pytest-cov pytest-xdist pytest-asyncio pytest-mock
pip install flask-testing responses freezegun
```

## Environment Variables

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
export TESTING=true
```

## Coverage Target

**Target: ≥90% coverage**

Check coverage:
```bash
pytest tests/integration/ --cov=copilot_core --cov-fail-under=90
```

## CI/CD Integration

Tests run automatically on:
- Every push to `main` or `dev`
- Every pull request
- Tag pushes (release automation)

See `.github/workflows/ci.yml` for pipeline configuration.

## Best Practices

1. **Test Isolation** - Each test should be independent
2. **Fixtures** - Use fixtures for setup, not test code
3. **Assertions** - Clear, specific assertions
4. **Naming** - Descriptive test names (what + expected result)
5. **Cleanup** - Always clean up resources (use fixtures)

## Troubleshooting

### Test fails with connection error
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Or start Neo4j
docker run -d --name neo4j -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/testpassword123 neo4j:5
```

### Tests too slow
```bash
# Run in parallel
pytest tests/integration/ -n auto
```

### Coverage not meeting target
```bash
# Check which lines are not covered
pytest tests/integration/ --cov=copilot_core --cov-report=term-missing
```

## Adding New Tests

1. Create new test file: `test_feature_integration.py`
2. Add test class: `class TestFeatureIntegration:`
3. Add test methods: `def test_feature_behavior(self, ...):`
4. Use fixtures for setup
5. Run and verify coverage

Example:
```python
class TestNewFeatureIntegration:
    def test_feature_creation(self, test_client, valid_auth_token):
        headers = {'Authorization': f'Bearer {valid_auth_token}'}
        
        response = test_client.post('/api/feature', json={
            'name': 'Test Feature'
        }, headers=headers)
        
        assert response.status_code == 201
        assert response.get_json()['name'] == 'Test Feature'
```
