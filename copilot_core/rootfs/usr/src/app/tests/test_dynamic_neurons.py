"""Tests for DynamicNeuronFactory and DynamicMetaNeuron.

Covers:
- Proposal creation (manual and from patterns)
- Neuron creation and registration
- Connection generation
- Relevance decay and removal
- Safety bounds (max neurons, min confidence)
- Persistence (save/load)
- DynamicMetaNeuron evaluation
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from copilot_core.neurons.dynamic import (
    DynamicMetaNeuron,
    DynamicNeuronFactory,
    ProposedNeuron,
    MAX_DYNAMIC_NEURONS,
    MIN_PROPOSAL_CONFIDENCE,
    MIN_RELEVANCE,
    RELEVANCE_DECAY_RATE,
)
from copilot_core.neurons.base import NeuronConfig, NeuronType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_persist_path(tmp_path):
    """Temporary file for neuron persistence."""
    return str(tmp_path / "dynamic_neurons.json")


@pytest.fixture
def mock_bus():
    """Mock IntegrationBus."""
    bus = MagicMock()
    bus.subscribe = MagicMock(return_value="sub-123")
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def mock_cross_analyzer():
    """Mock CrossModuleAnalyzer."""
    analyzer = MagicMock()
    analyzer.get_patterns = MagicMock(return_value=[])
    return analyzer


@pytest.fixture
def mock_neuron_manager():
    """Mock NeuronManager."""
    manager = MagicMock()
    manager.add_neuron = MagicMock()
    return manager


@pytest.fixture
def factory(mock_bus, mock_cross_analyzer, mock_neuron_manager, tmp_persist_path):
    """DynamicNeuronFactory with mocked dependencies."""
    return DynamicNeuronFactory(
        bus=mock_bus,
        cross_analyzer=mock_cross_analyzer,
        neuron_manager=mock_neuron_manager,
        persist_path=tmp_persist_path,
    )


@pytest.fixture
def sample_proposal():
    """A valid ProposedNeuron."""
    return ProposedNeuron(
        neuron_id="dynamic.presence_x_energy",
        name="meta.presence_energy",
        description="Aggregation of presence and energy patterns",
        source_neurons=["context.presence", "state.energy_level"],
        weights={"context.presence": 0.8, "state.energy_level": 0.7},
        confidence=0.85,
        pattern_ids=["context.presence~state.energy_level"],
    )


# ---------------------------------------------------------------------------
# ProposedNeuron Tests
# ---------------------------------------------------------------------------


class TestProposedNeuron:
    """Tests for ProposedNeuron dataclass."""

    def test_to_dict(self, sample_proposal):
        d = sample_proposal.to_dict()
        assert d["neuron_id"] == "dynamic.presence_x_energy"
        assert d["name"] == "meta.presence_energy"
        assert d["confidence"] == 0.85
        assert len(d["source_neurons"]) == 2
        assert "proposed_at_ms" in d

    def test_default_timestamp(self):
        p = ProposedNeuron(
            neuron_id="test",
            name="test",
            description="test",
            source_neurons=[],
            weights={},
            confidence=1.0,
        )
        assert p.proposed_at_ms > 0


# ---------------------------------------------------------------------------
# DynamicMetaNeuron Tests
# ---------------------------------------------------------------------------


class TestDynamicMetaNeuron:
    """Tests for DynamicMetaNeuron evaluation and serialization."""

    def _make_neuron(self):
        config = NeuronConfig(
            name="meta.test",
            neuron_type=NeuronType.STATE,
            weights={"context.presence": 0.8, "state.energy_level": 0.6},
        )
        return DynamicMetaNeuron(
            config=config,
            source_neurons=["context.presence", "state.energy_level"],
            source_weights={"context.presence": 0.8, "state.energy_level": 0.6},
        )

    def test_evaluate_weighted_average(self):
        neuron = self._make_neuron()
        context = {
            "neurons": {
                "context.presence": {"value": 1.0, "confidence": 0.9},
                "state.energy_level": {"value": 0.5, "confidence": 0.8},
            }
        }
        result = neuron.evaluate(context)
        # weighted: (1.0*0.8 + 0.5*0.6) / (0.8+0.6) = 1.1/1.4 ≈ 0.786
        assert 0.75 < result < 0.80

    def test_evaluate_missing_sources(self):
        neuron = self._make_neuron()
        context = {"neurons": {}}
        result = neuron.evaluate(context)
        assert result == 0.0

    def test_evaluate_partial_sources(self):
        neuron = self._make_neuron()
        context = {
            "neurons": {
                "context.presence": {"value": 0.6, "confidence": 0.9},
            }
        }
        result = neuron.evaluate(context)
        # Only presence available: (0.6*0.8) / (0.8) = 0.6
        # energy_level missing -> contributes 0
        # Actually: (0.6*0.8 + 0.0*0.6) / (0.8+0.6) = 0.48/1.4 ≈ 0.343
        assert 0.3 < result < 0.4

    def test_evaluate_clamped_to_bounds(self):
        neuron = self._make_neuron()
        context = {
            "neurons": {
                "context.presence": {"value": 5.0, "confidence": 1.0},
                "state.energy_level": {"value": 5.0, "confidence": 1.0},
            }
        }
        result = neuron.evaluate(context)
        assert result <= 1.0

    def test_to_dict_includes_dynamic_flag(self):
        neuron = self._make_neuron()
        d = neuron.to_dict()
        assert d["dynamic"] is True
        assert "source_neurons" in d
        assert "relevance" in d

    def test_from_config(self):
        config = NeuronConfig(
            name="meta.from_config",
            neuron_type=NeuronType.STATE,
            weights={"context.presence": 0.5, "state.comfort_index": 0.3},
        )
        neuron = DynamicMetaNeuron.from_config(config)
        assert set(neuron.source_neurons) == {"context.presence", "state.comfort_index"}

    def test_evaluation_count_increments(self):
        neuron = self._make_neuron()
        context = {
            "neurons": {
                "context.presence": {"value": 0.5, "confidence": 1.0},
                "state.energy_level": {"value": 0.5, "confidence": 1.0},
            }
        }
        assert neuron._evaluation_count == 0
        neuron.evaluate(context)
        assert neuron._evaluation_count == 1
        neuron.evaluate(context)
        assert neuron._evaluation_count == 2


# ---------------------------------------------------------------------------
# DynamicNeuronFactory Tests
# ---------------------------------------------------------------------------


class TestDynamicNeuronFactory:
    """Tests for DynamicNeuronFactory lifecycle."""

    def test_init_subscribes_to_bus(self, factory, mock_bus):
        mock_bus.subscribe.assert_called_once_with(
            "pattern.discovered", factory._on_pattern_discovered
        )

    def test_init_without_bus(self, tmp_persist_path):
        factory = DynamicNeuronFactory(persist_path=tmp_persist_path)
        assert factory.get_stats()["dynamic_neurons_count"] == 0

    def test_propose_neuron_manual(self, factory):
        proposal = factory.propose_neuron(
            source_neurons=["context.presence", "state.energy_level"],
            weights={"context.presence": 0.8, "state.energy_level": 0.6},
            name="meta.presence_energy",
            confidence=0.9,
        )
        assert proposal is not None
        assert proposal.neuron_id == "dynamic.presence_energy"
        assert proposal.confidence == 0.9

    def test_propose_neuron_rejected_low_confidence(self, factory):
        proposal = factory.propose_neuron(
            source_neurons=["a", "b"],
            weights={"a": 0.5, "b": 0.5},
            name="meta.low",
            confidence=0.3,
        )
        assert proposal is None

    def test_create_neuron(self, factory, sample_proposal, mock_neuron_manager):
        neuron = factory.create_neuron(sample_proposal)
        assert neuron is not None
        assert isinstance(neuron, DynamicMetaNeuron)
        mock_neuron_manager.add_neuron.assert_called_once()

    def test_create_neuron_publishes_event(self, factory, sample_proposal, mock_bus):
        factory.create_neuron(sample_proposal)
        mock_bus.publish.assert_called_once()
        call_args = mock_bus.publish.call_args
        assert call_args[0][0] == "neuron.dynamic_created"

    def test_create_neuron_idempotent(self, factory, sample_proposal):
        n1 = factory.create_neuron(sample_proposal)
        n2 = factory.create_neuron(sample_proposal)
        assert n1 is n2
        assert factory.get_stats()["dynamic_neurons_count"] == 1

    def test_max_neurons_limit(self, factory):
        for i in range(MAX_DYNAMIC_NEURONS):
            proposal = ProposedNeuron(
                neuron_id=f"dynamic.test_{i}",
                name=f"meta.test_{i}",
                description=f"Test neuron {i}",
                source_neurons=["a", "b"],
                weights={"a": 0.5, "b": 0.5},
                confidence=0.9,
            )
            result = factory.create_neuron(proposal)
            assert result is not None

        # One more should be rejected
        overflow = ProposedNeuron(
            neuron_id="dynamic.overflow",
            name="meta.overflow",
            description="Should be rejected",
            source_neurons=["a", "b"],
            weights={"a": 0.5, "b": 0.5},
            confidence=0.9,
        )
        assert factory.create_neuron(overflow) is None
        assert factory.get_stats()["dynamic_neurons_count"] == MAX_DYNAMIC_NEURONS

    def test_remove_neuron(self, factory, sample_proposal):
        factory.create_neuron(sample_proposal)
        assert factory.remove_neuron(sample_proposal.neuron_id) is True
        assert factory.get_stats()["dynamic_neurons_count"] == 0

    def test_remove_nonexistent(self, factory):
        assert factory.remove_neuron("nonexistent") is False

    def test_connect_to_existing(self, factory, sample_proposal):
        factory.create_neuron(sample_proposal)
        connections = factory.connect_to_existing(sample_proposal.neuron_id)
        assert len(connections) == 2
        from_neurons = [c[0] for c in connections]
        assert "context.presence" in from_neurons
        assert "state.energy_level" in from_neurons
        assert all(c[1] == sample_proposal.neuron_id for c in connections)

    def test_connect_nonexistent(self, factory):
        assert factory.connect_to_existing("nonexistent") == []


class TestDynamicNeuronFactoryDecay:
    """Tests for relevance decay and automatic removal."""

    def test_decay_reduces_relevance(self, factory, sample_proposal):
        neuron = factory.create_neuron(sample_proposal)
        initial = neuron.relevance
        factory.decay_relevance()
        assert neuron.relevance < initial

    def test_decay_removes_below_threshold(self, factory):
        proposal = ProposedNeuron(
            neuron_id="dynamic.weak",
            name="meta.weak",
            description="Low relevance neuron",
            source_neurons=["a"],
            weights={"a": 0.5},
            confidence=0.8,
        )
        neuron = factory.create_neuron(proposal)
        # Force relevance below threshold
        neuron.relevance = MIN_RELEVANCE * 0.5
        removed = factory.decay_relevance()
        assert "dynamic.weak" in removed
        assert factory.get_stats()["dynamic_neurons_count"] == 0


class TestDynamicNeuronFactoryPatterns:
    """Tests for pattern-based proposal generation."""

    def test_propose_from_strong_patterns(self, factory, mock_cross_analyzer):
        mock_cross_analyzer.get_patterns.return_value = [
            {
                "pattern_id": "context.presence~state.energy_level",
                "module_a": "context.presence",
                "module_b": "state.energy_level",
                "correlation": 0.85,
                "co_occurrence_count": 50,
                "description": "Strong correlation",
            }
        ]
        proposals = factory.propose_neuron_from_patterns()
        assert len(proposals) == 1
        assert proposals[0].confidence == 0.85

    def test_skip_weak_patterns(self, factory, mock_cross_analyzer):
        mock_cross_analyzer.get_patterns.return_value = [
            {
                "pattern_id": "weak~pattern",
                "module_a": "context.a",
                "module_b": "state.b",
                "correlation": 0.3,
                "co_occurrence_count": 5,
                "description": "Weak",
            }
        ]
        proposals = factory.propose_neuron_from_patterns()
        assert len(proposals) == 0

    def test_skip_existing_neurons(self, factory, mock_cross_analyzer):
        # First create a neuron from the pattern
        mock_cross_analyzer.get_patterns.return_value = [
            {
                "pattern_id": "context.presence~state.energy_level",
                "module_a": "context.presence",
                "module_b": "state.energy_level",
                "correlation": 0.85,
                "co_occurrence_count": 50,
                "description": "First discovery",
            }
        ]
        proposals = factory.propose_neuron_from_patterns()
        assert len(proposals) == 1
        factory.create_neuron(proposals[0])

        # Same pattern again should be skipped
        mock_cross_analyzer.get_patterns.return_value = [
            {
                "pattern_id": "context.presence~state.energy_level",
                "module_a": "context.presence",
                "module_b": "state.energy_level",
                "correlation": 0.9,
                "co_occurrence_count": 100,
                "description": "Already exists",
            }
        ]
        proposals2 = factory.propose_neuron_from_patterns()
        assert len(proposals2) == 0


class TestDynamicNeuronFactoryPersistence:
    """Tests for save/load persistence."""

    def test_persist_and_reload(self, mock_bus, mock_cross_analyzer, mock_neuron_manager, tmp_persist_path):
        # Create and persist
        factory1 = DynamicNeuronFactory(
            bus=mock_bus,
            cross_analyzer=mock_cross_analyzer,
            neuron_manager=mock_neuron_manager,
            persist_path=tmp_persist_path,
        )
        proposal = ProposedNeuron(
            neuron_id="dynamic.persist_test",
            name="meta.persist_test",
            description="Persistence test",
            source_neurons=["context.a", "state.b"],
            weights={"context.a": 0.7, "state.b": 0.5},
            confidence=0.9,
        )
        factory1.create_neuron(proposal)
        assert os.path.exists(tmp_persist_path)

        # Reload in new factory
        factory2 = DynamicNeuronFactory(
            persist_path=tmp_persist_path,
        )
        assert factory2.get_stats()["dynamic_neurons_count"] == 1
        neurons = factory2.get_dynamic_neurons()
        assert len(neurons) == 1
        assert neurons[0]["source_neurons"] == ["context.a", "state.b"]

    def test_load_missing_file(self, tmp_persist_path):
        factory = DynamicNeuronFactory(
            persist_path=tmp_persist_path + "_missing",
        )
        assert factory.get_stats()["dynamic_neurons_count"] == 0

    def test_load_corrupt_file(self, tmp_persist_path):
        with open(tmp_persist_path, "w") as f:
            f.write("{invalid json")
        factory = DynamicNeuronFactory(persist_path=tmp_persist_path)
        assert factory.get_stats()["dynamic_neurons_count"] == 0


class TestDynamicNeuronFactoryStats:
    """Tests for statistics and API outputs."""

    def test_get_stats(self, factory, sample_proposal):
        stats = factory.get_stats()
        assert stats["dynamic_neurons_count"] == 0
        assert stats["max_neurons"] == MAX_DYNAMIC_NEURONS

        factory.create_neuron(sample_proposal)
        stats = factory.get_stats()
        assert stats["dynamic_neurons_count"] == 1
        assert sample_proposal.neuron_id in stats["neuron_ids"]

    def test_get_dynamic_neurons(self, factory, sample_proposal):
        assert factory.get_dynamic_neurons() == []
        factory.create_neuron(sample_proposal)
        neurons = factory.get_dynamic_neurons()
        assert len(neurons) == 1
        assert neurons[0]["dynamic"] is True

    def test_get_proposals(self, factory):
        factory.propose_neuron(
            source_neurons=["a", "b"],
            weights={"a": 0.5, "b": 0.5},
            name="meta.test",
            confidence=0.9,
        )
        proposals = factory.get_proposals()
        assert len(proposals) == 1
        assert proposals[0]["name"] == "meta.test"
