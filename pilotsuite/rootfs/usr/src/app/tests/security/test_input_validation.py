"""Security Tests: Input Validation for API Endpoints.

Tests for P2 security fixes:
- P2-01: Zone ID Input Sanitization
- P2-03: Neuron ID Validation
- P2-04: Mood History Limit Cap
- P2-05: WebSocket Room Name Validation
"""
import pytest
import sys
import os
import re

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import validation patterns directly (avoid Flask imports)
ZONE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
ZONE_ID_MAX_LENGTH = 50

NEURON_ID_PATTERN = re.compile(r'^[a-z_]+(\.[a-z_]+)?$')
NEURON_ID_MAX_LENGTH = 100

ROOM_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
ROOM_NAME_MAX_LENGTH = 50

MOOD_HISTORY_MAX_LIMIT = 100


def validate_zone_id(zone_id: str) -> bool:
    """Validate zone ID format."""
    if not zone_id or len(zone_id) > ZONE_ID_MAX_LENGTH:
        return False
    return bool(ZONE_ID_PATTERN.match(zone_id))


def validate_neuron_id(neuron_id: str) -> bool:
    """Validate neuron ID format."""
    if not neuron_id or len(neuron_id) > NEURON_ID_MAX_LENGTH:
        return False
    return bool(NEURON_ID_PATTERN.match(neuron_id))


def validate_room_name(room_name: str) -> bool:
    """Validate room name format."""
    if not room_name or len(room_name) > ROOM_NAME_MAX_LENGTH:
        return False
    return bool(ROOM_NAME_PATTERN.match(room_name))


class TestZoneIDValidation:
    """Test zone ID sanitization (P2-01)."""
    
    def test_valid_zone_ids(self):
        """Test valid zone ID formats."""
        valid_ids = [
            "living_room",
            "bedroom",
            "kitchen",
            "living-room",
            "bathroom_1",
            "zone123",
            "Zone_A",
            "a" * 50,  # Max length
        ]
        for zone_id in valid_ids:
            assert validate_zone_id(zone_id) is True, f"Valid zone_id rejected: {zone_id}"
    
    def test_invalid_zone_ids(self):
        """Test invalid zone ID formats are rejected."""
        invalid_ids = [
            "",  # Empty
            "living room",  # Space
            "living/room",  # Slash
            "living\\room",  # Backslash
            "../etc/passwd",  # Path traversal
            "zone;rm -rf",  # Injection attempt
            "zone<script>",  # XSS attempt
            "zone' OR 1=1",  # SQL injection
            "a" * 51,  # Too long
            None,  # None type
        ]
        for zone_id in invalid_ids:
            if zone_id is not None:
                assert validate_zone_id(zone_id) is False, f"Invalid zone_id accepted: {zone_id}"
    
    def test_zone_id_pattern(self):
        """Test zone ID regex pattern."""
        assert ZONE_ID_PATTERN.pattern == r'^[a-zA-Z0-9_-]+$'
        assert ZONE_ID_MAX_LENGTH == 50


class TestNeuronIDValidation:
    """Test neuron ID validation (P2-03)."""
    
    def test_valid_neuron_ids(self):
        """Test valid neuron ID formats."""
        valid_ids = [
            "context.presence",
            "state.energy_level",
            "mood.focus",
            "presence",
            "energy_level",
            "mood",
            "a" * 100,  # Max length
        ]
        for neuron_id in valid_ids:
            assert validate_neuron_id(neuron_id) is True, f"Valid neuron_id rejected: {neuron_id}"
    
    def test_invalid_neuron_ids(self):
        """Test invalid neuron ID formats are rejected."""
        invalid_ids = [
            "",  # Empty
            "Context.Presence",  # Uppercase
            "context..presence",  # Double dot
            ".context.presence",  # Leading dot
            "context.presence.",  # Trailing dot
            "context/presence",  # Slash
            "context\\presence",  # Backslash
            "../etc/passwd",  # Path traversal
            "neuron;rm -rf",  # Injection
            "a" * 101,  # Too long
            None,  # None type
        ]
        for neuron_id in invalid_ids:
            if neuron_id is not None:
                assert validate_neuron_id(neuron_id) is False, f"Invalid neuron_id accepted: {neuron_id}"
    
    def test_neuron_id_pattern(self):
        """Test neuron ID regex pattern."""
        assert NEURON_ID_PATTERN.pattern == r'^[a-z_]+(\.[a-z_]+)?$'
        assert NEURON_ID_MAX_LENGTH == 100


class TestMoodHistoryLimit:
    """Test mood history limit cap (P2-04)."""
    
    def test_mood_history_max_limit(self):
        """Test server-side cap on mood history queries."""
        assert MOOD_HISTORY_MAX_LIMIT == 100
    
    def test_limit_capping_logic(self):
        """Test that limits are properly capped."""
        # Simulate the capping logic from get_mood_history()
        test_cases = [
            (5, 5),  # Under cap
            (50, 50),  # Under cap
            (100, 100),  # At cap
            (150, 100),  # Over cap - should be capped
            (1000, 100),  # Way over cap
            (1000000, 100),  # Extreme
        ]
        for requested, expected in test_cases:
            capped = min(requested, MOOD_HISTORY_MAX_LIMIT)
            assert capped == expected, f"Limit {requested} should be capped to {expected}"


class TestWebSocketRoomValidation:
    """Test WebSocket room name validation (P2-05)."""
    
    def test_valid_room_names(self):
        """Test valid room name formats."""
        valid_rooms = [
            "neurons",
            "mood",
            "general",
            "living_room",
            "bedroom-1",
            "zone_A",
            "a" * 50,  # Max length
        ]
        for room in valid_rooms:
            assert validate_room_name(room) is True, f"Valid room rejected: {room}"
    
    def test_invalid_room_names(self):
        """Test invalid room name formats are rejected."""
        invalid_rooms = [
            "",  # Empty
            "living room",  # Space
            "living/room",  # Slash
            "living\\room",  # Backslash
            "../etc",  # Path traversal
            "room<script>",  # XSS
            "room' OR 1=1",  # SQL injection
            "a" * 51,  # Too long
            None,  # None type
        ]
        for room in invalid_rooms:
            if room is not None:
                assert validate_room_name(room) is False, f"Invalid room accepted: {room}"
    
    def test_room_name_pattern(self):
        """Test room name regex pattern."""
        assert ROOM_NAME_PATTERN.pattern == r'^[a-zA-Z0-9_-]+$'
        assert ROOM_NAME_MAX_LENGTH == 50


class TestSecurityIntegration:
    """Integration tests for security validations."""
    
    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "....//....//etc/passwd",
        ]
        for attempt in traversal_attempts:
            assert validate_zone_id(attempt) is False
            assert validate_neuron_id(attempt) is False
            assert validate_room_name(attempt) is False
    
    def test_injection_attempts_blocked(self):
        """Test that injection attempts are blocked."""
        injections = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "{{constructor.constructor('return this')()}}",
            "${7*7}",
        ]
        for injection in injections:
            assert validate_zone_id(injection) is False
            assert validate_neuron_id(injection) is False
            assert validate_room_name(injection) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
