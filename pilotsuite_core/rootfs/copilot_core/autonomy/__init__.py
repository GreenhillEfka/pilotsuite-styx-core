"""Autonomy Module — Core Business Logic für Zone Automation.

ARCHITEKTUR:
- CORE = Business Logic, Rules, Engine, Habitus Learning
- HA  = Nur Darstellung, Konfiguration, Events an Core

Dieses Modul enthällt die GESAMTE Automation-Logik:
1. ZoneAutomationController — Haupt-Controller
2. NeuronStatusTracker — Neuron-Zustände
3. AutomationRuleEngine — Rule-Engine
4. HabitusIntegration — Learning

HA ruft NUR APIs auf, keine Logik in HA!
"""

from .zone_automation_controller import (
    ZoneAutomationController,
    ZoneAutomationConfig,
    AutomationMode,
    NeuronMode,
    LightAutomationConfig,
    NeuronStatus,
    NeuronStatusTracker,
    AutomationRule,
    AutomationRuleEngine,
    get_zone_automation_controller,
)

__all__ = [
    "ZoneAutomationController",
    "ZoneAutomationConfig",
    "AutomationMode",
    "NeuronMode",
    "LightAutomationConfig",
    "NeuronStatus",
    "NeuronStatusTracker",
    "AutomationRule",
    "AutomationRuleEngine",
    "get_zone_automation_controller",
]
