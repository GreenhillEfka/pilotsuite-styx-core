"""Tests for neuron input validation."""

import pytest
from datetime import datetime
from copilot_core.neurons.input_validator import (
    NeuronInputValidator, validate_and_normalize_context, 
    validate_ha_state, validate_entity_ids
)


class TestNeuronInputValidator:
    """Tests for the NeuronInputValidator class."""
    
    def test_validate_context_with_empty_input(self):
        """Test context validation with empty input."""
        validator = NeuronInputValidator()
        result = validator.validate_context({})
        
        # Should have all required keys
        assert "states" in result
        assert "now" in result
        assert "presence" in result
        assert "sun" in result
        assert "weather" in result
        assert "history" in result
        assert "neurons" in result
        assert "household" in result
        assert "present_persons" in result
    
    def test_validate_context_with_partial_input(self):
        """Test context validation with partial input."""
        validator = NeuronInputValidator()
        input_context = {
            "states": {"sensor.test": {"state": "on"}},
            "presence": {"living_room": True}
        }
        result = validator.validate_context(input_context)
        
        # Should preserve existing values
        assert result["states"] == input_context["states"]
        assert result["presence"] == input_context["presence"]
        
        # Should add missing keys
        assert "now" in result
        assert "sun" in result
        assert "weather" in result
        assert "history" in result
        assert "neurons" in result
        assert "household" in result
        assert "present_persons" in result
    
    def test_validate_context_with_invalid_states(self):
        """Test context validation with invalid states."""
        validator = NeuronInputValidator()
        input_context = {
            "states": "invalid_type"
        }
        result = validator.validate_context(input_context)
        
        # Should convert invalid states to empty dict
        assert result["states"] == {}
    
    def test_validate_ha_state_with_string(self):
        """Test HA state validation with string input."""
        result = validate_ha_state("on", "light.test")
        
        assert result["state"] == "on"
        assert result["attributes"] == {}
        assert result["last_updated"] is None
        assert result["last_changed"] is None
    
    def test_validate_ha_state_with_dict(self):
        """Test HA state validation with dict input."""
        input_state = {
            "state": "on",
            "attributes": {"brightness": 100},
            "last_updated": "2023-01-01T00:00:00Z",
            "last_changed": "2023-01-01T00:00:00Z"
        }
        result = validate_ha_state(input_state, "light.test")
        
        assert result["state"] == "on"
        assert result["attributes"] == {"brightness": 100}
        assert result["last_updated"] == "2023-01-01T00:00:00Z"
        assert result["last_changed"] == "2023-01-01T00:00:00Z"
    
    def test_validate_ha_state_with_invalid_attributes(self):
        """Test HA state validation with invalid attributes."""
        input_state = {
            "state": "on",
            "attributes": "invalid_type"
        }
        result = validate_ha_state(input_state, "light.test")
        
        # Should convert invalid attributes to empty dict
        assert result["attributes"] == {}
    
    def test_validate_ha_state_with_other_type(self):
        """Test HA state validation with other type."""
        result = validate_ha_state(123, "sensor.test")
        
        # Should convert to string
        assert result["state"] == "123"
    
    def test_validate_entity_id_with_valid_ids(self):
        """Test entity ID validation with valid IDs."""
        validator = NeuronInputValidator()
        
        assert validator.validate_entity_id("light.test") is True
        assert validator.validate_entity_id("sensor.temperature") is True
        assert validator.validate_entity_id("switch.kitchen_light") is True
        assert validator.validate_entity_id("person.john_doe") is True
    
    def test_validate_entity_id_with_invalid_ids(self):
        """Test entity ID validation with invalid IDs."""
        validator = NeuronInputValidator()
        
        assert validator.validate_entity_id("") is False
        assert validator.validate_entity_id("invalid") is False
        assert validator.validate_entity_id("domain.with.three.parts") is False
        assert validator.validate_entity_id("domain with spaces") is False
        assert validator.validate_entity_id("domain.special!chars") is False
        assert validator.validate_entity_id(123) is False
        assert validator.validate_entity_id(None) is False
    
    def test_sanitize_entity_ids_with_valid_list(self):
        """Test sanitizing entity IDs with valid list."""
        validator = NeuronInputValidator()
        input_ids = ["light.test", "sensor.temperature", "switch.kitchen_light"]
        result = validator.sanitize_entity_ids(input_ids)
        
        assert result == input_ids
    
    def test_sanitize_entity_ids_with_mixed_list(self):
        """Test sanitizing entity IDs with mixed valid/invalid list."""
        validator = NeuronInputValidator()
        input_ids = ["light.test", "invalid", "sensor.temperature", ""]
        result = validator.sanitize_entity_ids(input_ids)
        
        # Should only include valid IDs
        assert result == ["light.test", "sensor.temperature"]
    
    def test_sanitize_entity_ids_with_invalid_input(self):
        """Test sanitizing entity IDs with invalid input."""
        validator = NeuronInputValidator()
        result = validator.sanitize_entity_ids("not_a_list")
        
        # Should return empty list
        assert result == []


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_validate_and_normalize_context(self):
        """Test the validate_and_normalize_context convenience function."""
        input_context = {
            "states": {"sensor.test": {"state": "on"}}
        }
        result = validate_and_normalize_context(input_context)
        
        # Should have all required keys
        assert "states" in result
        assert "now" in result
        assert result["states"] == input_context["states"]
    
    def test_validate_entity_ids_convenience(self):
        """Test the validate_entity_ids convenience function."""
        input_ids = ["light.test", "invalid", "sensor.temperature"]
        result = validate_entity_ids(input_ids)
        
        # Should only include valid IDs
        assert result == ["light.test", "sensor.temperature"]


if __name__ == "__main__":
    pytest.main([__file__])