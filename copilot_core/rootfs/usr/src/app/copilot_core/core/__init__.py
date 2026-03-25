"""
Copilot Core — Truth Layers and Read Models.

This package provides the foundational truth layers for PilotSuite:
  - taxonomy.py:        Classification Authority (Entity Role/Tag/Module routing)
  - brain_read_model.py: Brain Growth Read Model (Graph + Neuron + Module context)
  - dashboard_read_models.py: Truth-backed Dashboard Read Models

Usage:
    from copilot_core.core.taxonomy import classify_entity
    from copilot_core.core.brain_read_model import get_brain_summary, feed_brain
    from copilot_core.core.dashboard_read_models import (
        ZoneSummaryReadModel,
        ZoneDetailReadModel,
        ModuleReadModel,
        SystemOverviewReadModel,
    )
"""

from .taxonomy import (
    EntityClassification,
    EntityRole,
    EntityTag,
    classify_entity,
    detect_entity_role,
    detect_entity_tags,
)
from .brain_read_model import (
    BrainActivitySnapshot,
    BrainGraphGrowth,
    NeuronSnapshot,
    build_brain_activity_snapshot,
    feed_brain,
    get_brain_summary,
    get_brain_activity_for_api,
    update_graph_growth_snapshot,
)
from .dashboard_read_models import (
    ReadModelMeta,
    ZoneSummaryReadModel,
    ZoneDetailReadModel,
    ModuleReadModel,
    SystemOverviewReadModel,
    build_zone_summary_read_model,
    build_zone_detail_read_model,
    build_module_read_model,
    build_system_overview_read_model,
)

__all__ = [
    # taxonomy
    "EntityClassification",
    "EntityRole",
    "EntityTag",
    "classify_entity",
    "detect_entity_role",
    "detect_entity_tags",
    # brain_read_model
    "BrainActivitySnapshot",
    "BrainGraphGrowth",
    "NeuronSnapshot",
    "build_brain_activity_snapshot",
    "feed_brain",
    "get_brain_summary",
    "get_brain_activity_for_api",
    "update_graph_growth_snapshot",
    # dashboard_read_models
    "ReadModelMeta",
    "ZoneSummaryReadModel",
    "ZoneDetailReadModel",
    "ModuleReadModel",
    "SystemOverviewReadModel",
    "build_zone_summary_read_model",
    "build_zone_detail_read_model",
    "build_module_read_model",
    "build_system_overview_read_model",
]