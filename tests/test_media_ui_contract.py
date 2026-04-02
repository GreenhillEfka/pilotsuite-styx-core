from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from copilot_core.api.v1.media_ui import media_ui_bp  # noqa: E402


def test_media_ui_blueprint_registers_expected_routes() -> None:
    app = Flask(__name__)
    app.register_blueprint(media_ui_bp)

    rules = {str(rule) for rule in app.url_map.iter_rules()}
    assert "/api/v1/media" in rules
    assert "/api/v1/media/sonos" in rules
    assert "/api/v1/media/sonos/favorites" in rules
    assert "/api/v1/media/musikwolke" in rules
    assert "/api/v1/media/cameras" in rules
