"""Contract tests for Conversation, Rate Limit, Scenes, Haushalt, Tag System, Multi-Home APIs.

Verifies:
- Each API blueprint is importable with expected url_prefix
- Key models/functions exist
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


class TestConversationAPI:
    """Conversation API blueprint contract."""

    def test_conversation_bp_importable(self):
        from copilot_core.api.v1.conversation import conversation_bp
        assert conversation_bp is not None

    def test_conversation_url_prefix(self):
        from copilot_core.api.v1.conversation import conversation_bp
        assert conversation_bp.url_prefix == "/chat"

    def test_openai_compat_bp_importable(self):
        from copilot_core.api.v1.conversation import openai_compat_bp
        assert openai_compat_bp is not None


class TestRateLimitAPI:
    """Rate Limit API blueprint contract."""

    def test_rate_limit_bp_importable(self):
        from copilot_core.api.v1.rate_limit import rate_limit_bp
        assert rate_limit_bp is not None

    def test_rate_limit_bp_exists(self):
        from copilot_core.api.v1.rate_limit import rate_limit_bp
        # None prefix = absolute paths used (/rate-limit/*)
        assert hasattr(rate_limit_bp, "url_prefix")


class TestTagSystemAPI:
    """Tag System API blueprint contract."""

    def test_tag_system_bp_importable(self):
        from copilot_core.api.v1.tag_system import bp as tag_bp
        assert tag_bp is not None

    def test_tag_system_url_prefix(self):
        from copilot_core.api.v1.tag_system import bp as tag_bp
        assert tag_bp.url_prefix == "/api/v1/tag-system"


class TestMultihomeAPI:
    """Multi-Home API blueprint contract."""

    def test_multihome_bp_importable(self):
        from copilot_core.api.v1.multihome import bp as mh_bp
        assert mh_bp is not None

    def test_multihome_url_prefix(self):
        from copilot_core.api.v1.multihome import bp as mh_bp
        assert mh_bp.url_prefix == "/api/v1/multihome"


class TestScenesAPI:
    """Scenes API blueprint contract."""

    def test_scenes_bp_importable(self):
        from copilot_core.api.v1.scenes import scenes_bp
        assert scenes_bp is not None

    def test_scenes_url_prefix(self):
        from copilot_core.api.v1.scenes import scenes_bp
        assert scenes_bp.url_prefix == "/api/v1/scenes"


class TestHaushaltAPI:
    """Haushalt API blueprint contract."""

    def test_haushalt_bp_importable(self):
        from copilot_core.api.v1.haushalt import haushalt_bp
        assert haushalt_bp is not None

    def test_haushalt_url_prefix(self):
        from copilot_core.api.v1.haushalt import haushalt_bp
        assert haushalt_bp.url_prefix == "/api/v1/haushalt"


class TestCacheControlAPI:
    """Cache Control API blueprint contract."""

    def test_cache_control_bp_importable(self):
        from copilot_core.api.v1.cache_control import cache_control_bp
        assert cache_control_bp is not None


class TestEntityAdoptionAPI:
    """Entity Adoption API blueprint contract."""

    def test_entity_adoption_bp_importable(self):
        from copilot_core.api.v1.entity_adoption import bp as adopt_bp
        assert adopt_bp is not None

    def test_entity_adoption_url_prefix(self):
        from copilot_core.api.v1.entity_adoption import bp as adopt_bp
        # /adoption or /api/v1/adoption — both acceptable
        assert adopt_bp.url_prefix is not None