"""Contract coverage for Slice 18 action-closure summary surfaces."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.action_closure import get_action_closure_store  # noqa: E402
from copilot_core.api.v1.action_closure import action_closure_bp  # noqa: E402
from copilot_core.api.v1.zone_dashboard import _build_global_context, init_zone_dashboard_api  # noqa: E402
from copilot_core.core.action_closure_read_model import (  # noqa: E402
    build_action_closure_context_block,
    build_action_closure_summary_read_model,
)
from copilot_core.styx.chat_handler import ChatHandler  # noqa: E402


def setup_function() -> None:
    get_action_closure_store().clear()
    init_zone_dashboard_api()


def _seed_closures() -> None:
    store = get_action_closure_store()

    alpha = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:voice",
        action_id="action:voice",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-01T20:00:00+00:00",
    )
    store.record_feedback(alpha["closure_id"], feedback="worked_well", comment="passt")
    store.record_execution(
        alpha["closure_id"],
        outcome="executed",
        runtime_source="ha.adapter",
        result={"status": "ok"},
        executed_at="2026-04-01T20:05:00+00:00",
    )

    beta = store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:predictive",
        action_id="action:predictive",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-01T20:10:00+00:00",
    )
    store.record_execution(
        beta["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="timeout",
        executed_at="2026-04-01T20:12:00+00:00",
    )

    store.upsert(
        source="multizone.accepted",
        proposal_id="proposal:scene",
        action_id="action:scene",
        zone_id="zone:living",
        module_id="scene",
        subject_type="scene",
        subject_id="scene:arrival",
        accepted_at="2026-04-01T20:20:00+00:00",
    )


def _client() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["COPILOT_AUTH_TOKEN"] = "test-token"
    app.register_blueprint(action_closure_bp)
    return app


def test_action_closure_summary_read_model_aggregates_outcomes() -> None:
    _seed_closures()

    summary = build_action_closure_summary_read_model(get_action_closure_store()).to_dict()

    assert summary["contract"] == "ActionClosureSummaryV1"
    assert summary["total_closures"] == 3
    assert summary["open_count"] == 1
    assert summary["terminal_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["feedback_count"] == 1
    assert summary["states"]["accepted"] == 1
    assert summary["states"]["executed"] == 1
    assert summary["states"]["failed"] == 1
    assert summary["sources"]["voice.accepted"] == 1
    assert summary["zones"]["zone:living"] == 2
    assert summary["modules"]["light"] == 1
    assert summary["modules"]["scene"] == 1
    assert summary["recent_closures"][0]["closure_id"]
    assert summary["highlights"]


def test_action_closure_context_block_is_chat_ready() -> None:
    _seed_closures()

    context = build_action_closure_context_block(
        get_action_closure_store(),
        zone_id="zone:living",
        recent_limit=2,
    ).to_dict()

    assert context["contract"] == "ActionClosureContextBlockV1"
    assert context["summary"]["total_closures"] == 2
    assert context["summary"]["success_count"] == 1
    assert context["recent_closures"][0]["zone_id"] == "zone:living"
    assert any("Aktionsabschluesse" in line for line in context["context_lines"])


def test_action_closure_summary_and_context_api_surface() -> None:
    _seed_closures()
    app = _client()
    client = app.test_client()
    headers = {"Authorization": "Bearer test-token"}

    summary_response = client.get("/api/v1/action-closures/summary", headers=headers)
    assert summary_response.status_code == 200
    summary_body = summary_response.get_json()
    assert summary_body["summary"]["contract"] == "ActionClosureSummaryV1"
    assert summary_body["summary"]["total_closures"] == 3

    context_response = client.get(
        "/api/v1/action-closures/context?zone_id=zone:living&recent_limit=2",
        headers=headers,
    )
    assert context_response.status_code == 200
    context_body = context_response.get_json()
    assert context_body["context"]["contract"] == "ActionClosureContextBlockV1"
    assert context_body["context"]["summary"]["total_closures"] == 2
    assert len(context_body["context"]["recent_closures"]) == 2


def test_zone_dashboard_global_context_exposes_action_closure_summary() -> None:
    _seed_closures()

    ctx = _build_global_context()

    assert ctx["action_closures"]["total"] == 3
    assert ctx["action_closures"]["open"] == 1
    assert ctx["action_closures"]["successful"] == 1
    assert ctx["action_closures"]["problematic"] == 1
    assert ctx["action_closures"]["recent"]


def test_chat_handler_home_context_mentions_action_closure_summary() -> None:
    _seed_closures()
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {}

    with app.app_context():
        handler = ChatHandler()
        home_context = handler._build_home_context()

    assert "Aktionsabschluesse" in home_context
    assert "erfolgreich" in home_context
