import time
import pytest
from flask import Flask
from copilot_core.api.v1.backend_ui import backend_ui_bp, ModuleRegistry

class FakeZone:
    def __init__(self, enabled_modules=None, zone_type="living"):
        self.enabled_modules = set(enabled_modules or [])
        self.zone_type = zone_type

class FakeEngine:
    def __init__(self):
        self._zones = {
            "living": FakeZone({"presence", "light"}, zone_type="living"),
            "sleep": FakeZone({"light"}, zone_type="sleep"),
        }
    
    def get_overview(self):
        return {"zones": list(self._zones.keys())}

def test_backend_ui_performance_baseline(monkeypatch):
    """Measure response time for all 10 backend tabs (Slice 134)."""
    # Mock the engine
    fake_engine = FakeEngine()
    monkeypatch.setattr("copilot_core.api.v1.backend_ui.HabitusZoneEngine", lambda: fake_engine)
    monkeypatch.setattr("copilot_core.api.v1.backend_ui.HAS_ENGINE", True)
    
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
        
        assert response.status_code == 200, f"Failed: {ep} -> {response.status_code}"
        results[ep] = duration
        
    # Threshold: Each tab should respond < 50ms (local/mocked)
    # Exception: RAG tab may be slower due to RAGStore initialization (< 200ms acceptable)
    for ep, duration in results.items():
        print(f"Performance: {ep} -> {duration:.2f}ms")
        if "/rag" in ep:
            assert duration < 200, f"Performance regression in {ep}: {duration:.2f}ms"
        else:
            assert duration < 50, f"Performance regression in {ep}: {duration:.2f}ms"

if __name__ == "__main__":
    pytest.main([__file__])
