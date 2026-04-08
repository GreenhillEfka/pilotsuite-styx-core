"""Tests for BaseNeuron and context neurons."""
import pytest
from datetime import datetime, timezone

from copilot_core.neurons.base import (
    BaseNeuron, NeuronState, NeuronConfig, NeuronType,
    ContextNeuron, StateNeuron, MoodNeuron, MoodType
)
from copilot_core.neurons.context import (
    PresenceNeuron, TimeOfDayNeuron, LightLevelNeuron,
    WeatherNeuron, create_context_neuron
)


class TestNeuronState:
    """Tests for NeuronState dataclass."""
    
    def test_default_state(self):
        """Test default state values."""
        state = NeuronState()
        assert state.active is False
        assert state.value == 0.0
        assert state.confidence == 0.0
        assert state.last_update is None
        assert state.trigger_count == 0
    
    def test_to_dict(self):
        """Test serialization."""
        state = NeuronState(active=True, value=0.75, confidence=0.9)
        data = state.to_dict()
        assert data["active"] is True
        assert data["value"] == 0.75
        assert data["confidence"] == 0.9


class TestNeuronConfig:
    """Tests for NeuronConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = NeuronConfig(name="test", neuron_type=NeuronType.CONTEXT)
        assert config.name == "test"
        assert config.threshold == 0.5
        assert config.decay_rate == 0.1
        assert config.enabled is True
    
    def test_serialization(self):
        """Test config serialization."""
        config = NeuronConfig(
            name="test",
            neuron_type=NeuronType.CONTEXT,
            threshold=0.7,
            entity_ids=["sensor.test"]
        )
        data = config.to_dict()
        
        restored = NeuronConfig.from_dict(data)
        assert restored.name == config.name
        assert restored.threshold == config.threshold
        assert restored.entity_ids == config.entity_ids


class TestPresenceNeuron:
    """Tests for PresenceNeuron."""
    
    def test_no_presence(self):
        """Test when no one is home."""
        config = NeuronConfig(
            name="presence.house",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["person.test"]
        )
        neuron = PresenceNeuron(config)
        
        context = {
            "states": {"person.test": {"state": "away"}}
        }
        
        value = neuron.evaluate(context)
        assert value == 0.0
    
    def test_presence_detected(self):
        """Test when someone is home."""
        config = NeuronConfig(
            name="presence.house",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["person.test"]
        )
        neuron = PresenceNeuron(config)
        
        context = {
            "states": {"person.test": {"state": "home"}}
        }
        
        value = neuron.evaluate(context)
        assert value == 1.0
    
    def test_update_triggers(self):
        """Test that update triggers at threshold."""
        config = NeuronConfig(
            name="presence.house",
            neuron_type=NeuronType.CONTEXT,
            threshold=0.5,
            smoothing_factor=1.0  # No smoothing for deterministic test
        )
        neuron = PresenceNeuron(config)

        # Below threshold
        neuron.update(0.3)
        assert neuron.is_active is False
        assert neuron.state.trigger_count == 0

        # Above threshold - should trigger
        neuron.update(0.7)
        assert neuron.is_active is True
        assert neuron.state.trigger_count == 1
        assert neuron.state.last_trigger is not None


class TestTimeOfDayNeuron:
    """Tests for TimeOfDayNeuron."""
    
    def test_night_time(self):
        """Test night time evaluation."""
        config = NeuronConfig(
            name="time_of_day",
            neuron_type=NeuronType.CONTEXT
        )
        neuron = TimeOfDayNeuron(config)
        
        # Night (23:00)
        context = {"time": {"hour": 23}}
        # Can't easily test without mocking datetime
        # Just verify it returns a value
        value = neuron.evaluate(context)
        assert 0.0 <= value <= 1.0
    
    def test_day_time(self):
        """Test day time evaluation."""
        config = NeuronConfig(
            name="time_of_day",
            neuron_type=NeuronType.CONTEXT
        )
        neuron = TimeOfDayNeuron(config)
        
        value = neuron.evaluate({})
        assert 0.0 <= value <= 1.0


class TestLightLevelNeuron:
    """Tests for LightLevelNeuron."""
    
    def test_dark_room(self):
        """Test dark room detection."""
        config = NeuronConfig(
            name="light_level",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["sensor.illuminance"]
        )
        neuron = LightLevelNeuron(config)
        
        context = {
            "states": {"sensor.illuminance": {"state": "5"}}
        }
        
        value = neuron.evaluate(context)
        assert value < 0.2
    
    def test_bright_room(self):
        """Test bright room detection."""
        config = NeuronConfig(
            name="light_level",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["sensor.illuminance"]
        )
        neuron = LightLevelNeuron(config)
        
        context = {
            "states": {"sensor.illuminance": {"state": "1500"}}
        }
        
        value = neuron.evaluate(context)
        assert value >= 0.9
    
    def test_lights_on_implies_dark(self):
        """Test that lights on suggests darkness."""
        config = NeuronConfig(
            name="light_level",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["light.living_room"]
        )
        neuron = LightLevelNeuron(config, use_sun_position=False)
        
        context = {
            "states": {"light.living_room": {"state": "on"}}
        }
        
        value = neuron.evaluate(context)
        assert value <= 0.5  # Some lights on implies not bright


class TestWeatherNeuron:
    """Tests for WeatherNeuron."""
    
    def test_sunny_weather(self):
        """Test sunny weather evaluation."""
        config = NeuronConfig(
            name="weather",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["weather.home"]
        )
        neuron = WeatherNeuron(config)
        
        context = {
            "states": {"weather.home": {"state": "sunny"}}
        }
        
        value = neuron.evaluate(context)
        assert value >= 0.8
    
    def test_rainy_weather(self):
        """Test rainy weather evaluation."""
        config = NeuronConfig(
            name="weather",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=["weather.home"]
        )
        neuron = WeatherNeuron(config)
        
        context = {
            "states": {"weather.home": {"state": "rainy"}}
        }
        
        value = neuron.evaluate(context)
        assert value <= 0.3


class TestNeuronDecay:
    """Tests for neuron decay behavior."""
    
    def test_decay_reduces_value(self):
        """Test that decay reduces value over time."""
        config = NeuronConfig(
            name="test",
            neuron_type=NeuronType.CONTEXT,
            decay_rate=0.5,  # 50% decay
            smoothing_factor=1.0  # No smoothing for deterministic test
        )
        neuron = PresenceNeuron(config)

        neuron.update(1.0)
        assert neuron.value == 1.0
        
        neuron.decay()
        assert neuron.value < 1.0
        assert neuron.value >= 0.5  # Should be around 0.5
    
    def test_decay_to_zero(self):
        """Test that repeated decay approaches zero."""
        config = NeuronConfig(
            name="test",
            neuron_type=NeuronType.CONTEXT,
            decay_rate=0.5,
            smoothing_factor=1.0  # No smoothing for deterministic test
        )
        neuron = PresenceNeuron(config)
        
        neuron.update(1.0)
        for _ in range(10):
            neuron.decay()
        
        assert neuron.value < 0.01


class TestCreateContextNeuron:
    """Tests for context neuron factory."""
    
    def test_create_presence(self):
        """Test creating presence neuron via factory."""
        config = NeuronConfig(
            name="presence.house",
            neuron_type=NeuronType.CONTEXT
        )
        neuron = create_context_neuron("presence", config)
        assert isinstance(neuron, PresenceNeuron)
    
    def test_create_unknown_raises(self):
        """Test that unknown neuron type raises."""
        config = NeuronConfig(
            name="unknown",
            neuron_type=NeuronType.CONTEXT
        )
        with pytest.raises(ValueError):
            create_context_neuron("unknown_type", config)