import time
import pytest
from flask import Flask
from copilot_core.api.v1.backend_ui import backend_ui_bp

def test_backend_ui_performance_baseline():
    """Measure response time for all 10 backend tabs (Slice 134)."""
    app = Flask(__name__)
    app.register_blueprint(backend_ui_bp)
    client = app.test_client()
    
    endpoints = [
        "/api/v1/backend/dashboard",
        "/api/v1/backend/zones",
        "/api/v1/backend/modules",
        "/api/v1/backend/brain",
        "/api/v1/backend/mood",
        "/api/v1/backend/automation",
        "/api/v1/backend/rag",
        "/api/v1/backend/media",
        "/api/v1/backend/hardware",
        "/api/v1/backend/system"
    ]
    
    results = {}
    for ep in endpoints:
        start_time = time.time()
        response = client.get(ep)
        duration = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        results[ep] = duration
        
    # Threshold: Each tab should respond < 50ms (local/mocked)
    for ep, duration in results.items():
        print(f"Performance: {ep} -> {duration:.2f}ms")
        assert duration < 50, f"Performance regression in {ep}: {duration:.2f}ms"

if __name__ == "__main__":
    pytest.main([__file__])
