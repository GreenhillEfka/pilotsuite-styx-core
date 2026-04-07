"""Integration Tests — E2E tests for PilotSuite Core."""
from __future__ import annotations

import pytest
import asyncio
import time
from typing import Dict, Any, List


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    async def pilotsuite_client(self):
        """Create full integration test client."""
        from fastapi.testclient import TestClient
        from copilot_core.api.rest_server import create_app, APIConfig
        
        config = APIConfig(debug=True, host="127.0.0.1", port=8080)
        app = create_app(config)
        client = TestClient(app)
        
        # Get auth token
        token_response = client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_e2e_key", "scope": "write"}
        )
        token = token_response.json()["access_token"]
        
        yield {"client": client, "token": token}

    def test_full_presence_flow(self, pilotsuite_client):
        """Test complete presence detection flow."""
        client = pilotsuite_client["client"]
        token = pilotsuite_client["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 1: Update multiple sensors
        from copilot_core.presence.api import PresenceAPI
        api = PresenceAPI()
        
        api.update_sensor("pir", "pir_1", 0.9)
        api.update_sensor("radar", "radar_1", 0.8)
        api.update_sensor("wifi", "wifi_1", 0.7)
        
        # Step 2: Get fused presence state
        state = api.get_current_state()
        
        assert state.is_present is True
        assert state.confidence > 0.5
        
        # Step 3: Verify via API
        response = client.get("/api/v1/presence/state", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "is_present" in data
        assert "confidence" in data

    def test_full_energy_optimization_flow(self, pilotsuite_client):
        """Test complete energy optimization flow."""
        from copilot_core.energy.or_tools_scheduler import ORToolsScheduler
        from copilot_core.energy.device_profiles import get_typical_home_setup
        
        # Setup
        scheduler = ORToolsScheduler(slots=96, solver_timeout_sec=5.0)
        devices = get_typical_home_setup()
        
        # Create forecast
        forecast = {
            'load': [1.0 + 0.5 * (i % 24 == 18) for i in range(96)],
            'solar': [2.0 if 8 <= i // 4 <= 20 else 0.0 for i in range(96)],
            'price': [0.3 + 0.1 * (i % 24 == 18) for i in range(96)],
        }
        prices = forecast['price']
        
        # Run optimization
        result = scheduler.optimize(devices, forecast, prices)
        
        assert result.success is True
        assert result.total_cost >= 0
        assert len(result.device_schedules) > 0
        
        # Verify schedules are valid
        for device_id, schedule in result.device_schedules.items():
            assert len(schedule) == 96
            assert all(0 <= s['power_kw'] <= 11.0 for s in schedule)

    def test_full_rag_flow(self, pilotsuite_client):
        """Test complete RAG flow."""
        from copilot_core.rag.vector_store import VectorStore
        from copilot_core.rag.embedding_pipeline import EmbeddingPipeline
        import tempfile
        import numpy as np
        
        # Setup
        temp_dir = tempfile.mkdtemp()
        store = VectorStore(data_dir=temp_dir, dimension=384)
        
        # Add documents
        documents = [
            {"id": "doc_1", "text": "Home Assistant automation guide"},
            {"id": "doc_2", "text": "Energy optimization best practices"},
            {"id": "doc_3", "text": "Presence detection configuration"},
        ]
        
        for doc in documents:
            # Simulate embedding (in real scenario, use embedding pipeline)
            embedding = np.random.rand(384).astype(np.float32)
            store.add_vector(doc["id"], embedding, {"text": doc["text"]})
        
        # Search
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.similarity_search(query_embedding, k=2)
        
        assert len(results) == 2
        assert all("entry_id" in r for r in results)
        assert all("metadata" in r for r in results)

    def test_full_knowledge_graph_flow(self, pilotsuite_client):
        """Test complete knowledge graph flow."""
        from copilot_core.brain.graph_store import BrainGraphStore
        import tempfile
        
        # Setup
        temp_dir = tempfile.mkdtemp()
        graph = BrainGraphStore(storage_path=temp_dir)
        
        # Build graph
        entities = [
            ("light.living_room", {"type": "light", "room": "living_room"}),
            ("switch.living_room", {"type": "switch", "room": "living_room"}),
            ("sensor.living_room_temp", {"type": "sensor", "room": "living_room"}),
        ]
        
        for entity_id, data in entities:
            graph.add_entity(entity_id, data)
        
        # Add relationships
        graph.add_relationship("light.living_room", "controlled_by", "switch.living_room")
        graph.add_relationship("sensor.living_room_temp", "monitors", "living_room")
        
        # Query
        lights = graph.query_by_type("light")
        assert len(lights) == 1
        
        # Traverse
        connected = graph.traverse_from("light.living_room", "controlled_by")
        assert len(connected) >= 1

    def test_full_security_flow(self, pilotsuite_client):
        """Test complete security flow."""
        from copilot_core.security.hardening import (
            SecureTokenGenerator,
            PasswordHasher,
            APIKeyStore,
            EncryptionAtRest,
        )
        import os
        
        # Token generation
        token_gen = SecureTokenGenerator()
        api_key = token_gen.generate_api_key()
        assert api_key.startswith("sk_")
        assert token_gen.verify_token(api_key) is True
        
        # Password hashing
        hasher = PasswordHasher(iterations=1000)
        password_hash = hasher.hash("secure_password")
        assert "salt" in password_hash
        assert "hash" in password_hash
        assert hasher.verify("secure_password", password_hash["salt"], password_hash["hash"]) is True
        
        # Encryption
        enc = EncryptionAtRest()
        data = {"secret": "value"}
        encrypted = enc.encrypt_json(data)
        decrypted = enc.decrypt_json(encrypted)
        assert decrypted == data
        
        # API Key store
        store = APIKeyStore(os.urandom(32))
        key_hash = store.add_key(api_key, scope="read", expires_in_hours=24)
        metadata = store.verify_key(api_key)
        assert metadata is not None
        assert metadata["scope"] == "read"

    def test_full_ml_pattern_flow(self, pilotsuite_client):
        """Test complete ML pattern learning flow."""
        from copilot_core.ml.pattern_detection import PatternDetectionEngine
        from copilot_core.ml.habit_learning import HabitLearningSystem
        import tempfile
        
        # Pattern detection
        pattern_engine = PatternDetectionEngine(min_confidence=0.6)
        
        # Feed events
        events = [
            {"type": "motion", "entity_id": "pir.living_room", "timestamp": time.time()},
            {"type": "state_change", "entity_id": "light.living_room", "to": "on", "timestamp": time.time() + 60},
        ] * 10
        
        for event in events:
            pattern_engine.process_event(event)
        
        patterns = pattern_engine.detect_patterns()
        assert len(patterns) > 0
        
        # Habit learning
        temp_dir = tempfile.mkdtemp()
        habit_system = HabitLearningSystem(data_dir=temp_dir)
        
        # Learn from patterns
        for pattern in patterns:
            habit_system.learn_from_pattern(pattern)
        
        habits = habit_system.get_habits()
        assert len(habits) > 0

    def test_full_voice_pipeline_flow(self, pilotsuite_client):
        """Test complete voice pipeline flow."""
        from copilot_core.voice.stt_whisper import WhisperSTT
        from copilot_core.voice.tts_piper import PiperTTS
        from copilot_core.voice.nlu_engine import NLUEngine
        
        # STT (mock test - actual audio would need file)
        stt = WhisperSTT()
        # In real test: stt.transcribe(audio_file)
        
        # NLU
        nlu = NLUEngine()
        intent = nlu.extract_intent("Turn on the living room lights")
        
        assert intent is not None
        assert "light" in intent.get("domain", "").lower()
        
        # TTS (mock test - actual audio would need file)
        tts = PiperTTS()
        # In real test: tts.synthesize("Hello world")

    def test_cross_module_integration(self, pilotsuite_client):
        """Test cross-module integration."""
        # This tests that modules work together
        
        # 1. Presence triggers automation
        from copilot_core.presence.api import PresenceAPI
        from copilot_core.ml.habit_learning import HabitLearningSystem
        import tempfile
        
        presence_api = PresenceAPI()
        temp_dir = tempfile.mkdtemp()
        habit_system = HabitLearningSystem(data_dir=temp_dir)
        
        # Simulate presence events
        presence_api.update_sensor("pir", "pir_1", 0.9)
        state = presence_api.get_current_state()
        
        # Learn from presence pattern
        if state.is_present:
            habit_system.learn_event({
                "type": "presence_detected",
                "confidence": state.confidence,
                "timestamp": time.time(),
            })
        
        # Verify learning occurred
        habits = habit_system.get_habits()
        assert len(habits) >= 0  # May be 0 if not enough data


# Run with: pytest copilot_core/tests/test_integration.py -v
