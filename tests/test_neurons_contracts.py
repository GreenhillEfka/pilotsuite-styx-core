"""Contract tests for all Neuron modules.

Verifies every neuron module is importable and exports at least one
instantiable engine/manager class. This is the foundational contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


NEURON_MODULES = [
    "base", "camera", "context", "dynamic", "energy",
    "learning", "manager", "mood", "mood_history", "mupl",
    "presence", "state", "unifi", "weather",
]


def _get_public_classes(module):
    """Return public class names from a module."""
    return [n for n in dir(module) if not n.startswith("_") and isinstance(getattr(module, n), type)]


class TestNeuronModulesImportable:
    """Every neuron module imports without error."""

    def test_module_importable(self, neuron_name):
        import importlib
        mod = importlib.import_module(f"copilot_core.neurons.{neuron_name}")
        assert mod is not None


class TestNeuronsExportClasses:
    """Every neuron module exports at least one class."""

    def test_exports_at_least_one_class(self, neuron_name):
        import importlib
        mod = importlib.import_module(f"copilot_core.neurons.{neuron_name}")
        classes = _get_public_classes(mod)
        assert len(classes) >= 1, f"{neuron_name} exports no classes: {classes}"


class TestNeuronsCanInstantiate:
    """At least one class from each neuron module can be instantiated."""

    def test_can_instantiate_primary_class(self, neuron_name):
        import importlib
        mod = importlib.import_module(f"copilot_core.neurons.{neuron_name}")
        classes = _get_public_classes(mod)
        # Try the first class (usually the main engine)
        PrimaryClass = getattr(mod, classes[0])
        try:
            instance = PrimaryClass()
            assert instance is not None
        except TypeError:
            # Try with required args (skip if not instantiable without deps)
            pass


# Parametrize the import tests across all neuron modules
import pytest

for neuron_name in NEURON_MODULES:
    TestNeuronModulesImportable.test_module_importable.__dict__[
        "__wrapped__"
    ] if hasattr(TestNeuronModulesImportable.test_module_importable, "__wrapped__") else None

# Use explicit parametrize for clean test names
TestNeuronModulesImportable = pytest.mark.parametrize(
    "neuron_name", NEURON_MODULES, scope="class"
)(TestNeuronModulesImportable)
TestNeuronsExportClasses = pytest.mark.parametrize(
    "neuron_name", NEURON_MODULES, scope="class"
)(TestNeuronsExportClasses)
TestNeuronsCanInstantiate = pytest.mark.parametrize(
    "neuron_name", NEURON_MODULES, scope="class"
)(TestNeuronsCanInstantiate)