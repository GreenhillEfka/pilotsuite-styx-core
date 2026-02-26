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


def test_dashboard_template_has_module_specs_for_media_light_scenes() -> None:
    text = _dashboard_template()
    assert "/api/v1/hub/media/config" in text
    assert "/api/v1/hub/light/config" in text
    assert "/api/v1/hub/scenes/config" in text


def test_dashboard_template_has_media_assignment_dropdown_controls() -> None:
    text = _dashboard_template()
    assert 'id="media-zone-select"' in text
    assert 'id="media-player-select"' in text
    assert "assignMediaPlayer" in text


def test_dashboard_template_exposes_neuron_brain_mode_and_synapse_view() -> None:
    text = _dashboard_template()
    assert 'id="brain-mode-neuron"' in text
    assert 'id="brain-mode-entity"' in text
    assert "setBrainMode('neuron')" in text
    assert "/api/v1/hub/brain/synapses" in text


def test_dashboard_template_exposes_event_log_chat_history_tabs() -> None:
    text = _dashboard_template()
    assert 'id="history-tabs"' in text
    assert "setHistoryTab('events')" in text
    assert "setHistoryTab('logs')" in text
    assert "/api/v1/events?limit=40" in text
    assert "/api/v1/dev/logs?limit=40" in text


def test_dashboard_template_exposes_homekit_zone_server_panel() -> None:
    text = _dashboard_template()
    assert 'id="hab-homekit-servers"' in text
    assert "syncHomeKitServers()" in text
    assert "loadHomeKitServers()" in text
    assert "/api/v1/homekit/servers" in text
    assert "/api/v1/homekit/toggle" in text


def test_dashboard_template_exposes_habitus_zone_recommendation_panel() -> None:
    text = _dashboard_template()
    assert 'id="hab-zone-recommendations"' in text
    assert "renderHabitusZoneRecommendations(" in text
    assert "applyZoneRecommendation(" in text
    assert "createZoneFromRecommendation(" in text
    assert "/api/v1/hub/habitus/management/recommendations" in text
    assert "/api/v1/hub/habitus/management/apply_zone" in text


def test_dashboard_template_has_resizable_module_config_windows() -> None:
    text = _dashboard_template()
    assert 'id="module-config-window-layer"' in text
    assert "openModuleConfigWindow(" in text
    assert "_bindModuleWindowDrag(" in text
    assert "resize:both" in text


def test_dashboard_template_exposes_system_overview_page() -> None:
    text = _dashboard_template()
    assert 'data-page="system"' in text
    assert 'id="page-system"' in text
    assert "loadSystemOverview(" in text
    assert "/api/v1/system/overview" in text


def test_dashboard_template_exposes_habitus_zone_status_summary() -> None:
    text = _dashboard_template()
    assert 'id="hab-zone-status-summary"' in text
    assert "loadHabitusZoneStatusSummary(" in text


def test_dashboard_template_exposes_self_repair_panel_on_system_page() -> None:
    text = _dashboard_template()
    assert 'id="self-repair-status"' in text
    assert 'id="self-repair-errors"' in text
    assert 'id="self-repair-jobs"' in text
    assert "runSelfCheck(" in text
    assert "createSelfRepairJob(" in text
    assert "connectSelfRepairGithub(" in text
    assert "prepareSelfRepairWorkspace(" in text
    assert "/api/v1/self-repair/status" in text
    assert "/api/v1/self-repair/jobs" in text
    assert "/api/v1/self-repair/github/test" in text
    assert "/api/v1/self-repair/workspace/prepare" in text
