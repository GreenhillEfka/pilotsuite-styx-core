"""Regression checks for Habitus zone handling in dashboard template."""

from pathlib import Path


def _dashboard_template() -> str:
    return (Path(__file__).resolve().parents[1] / "templates" / "dashboard.html").read_text(
        encoding="utf-8"
    )


def test_habitus_template_uses_hub_zone_api_routes() -> None:
    text = _dashboard_template()
    assert "/api/v1/hub/zones" in text
    assert "api('/api/v1/hub/zones')" in text


def test_habitus_template_exposes_room_multiselect() -> None:
    text = _dashboard_template()
    assert 'id="new-zone-rooms"' in text
    assert "Mehrfachauswahl" in text


def test_dashboard_template_detects_ingress_base_for_api_calls() -> None:
    text = _dashboard_template()
    assert "detectIngressBasePath" in text
    assert "hassio_ingress" in text
    assert "hassio\\/ingress" in text
    assert "const API=detectIngressBasePath()" in text


def test_dashboard_template_includes_module_config_panel() -> None:
    text = _dashboard_template()
    assert 'id="module-config-select"' in text
    assert "MODULE_CONFIG_SPECS" in text
    assert "loadSelectedModuleConfig" in text


def test_dashboard_template_uses_persistent_brain_chat_history() -> None:
    text = _dashboard_template()
    assert "/api/v1/hub/brain/activity/chat?limit=40" in text
    assert "/api/v1/hub/brain/activity/chat/clear" in text
    assert "persistChatMessage" in text


def test_dashboard_template_has_no_hardcoded_core_version_badge() -> None:
    text = _dashboard_template()
    assert 'id="ver-badge">v1.0.0<' not in text


def test_dashboard_template_exposes_chat_model_selector() -> None:
    text = _dashboard_template()
    assert 'id="chat-model-select"' in text
    assert "CHAT_MODEL_STORAGE_KEY" in text
    assert "_renderChatModelSelector" in text


def test_dashboard_template_exposes_llm_routing_controls() -> None:
    text = _dashboard_template()
    assert 'id="set-routing"' in text
    assert "saveRoutingConfig" in text
    assert "/chat/routing" in text
