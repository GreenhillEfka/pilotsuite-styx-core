from __future__ import annotations

from pathlib import Path

from flask import Flask

from dashboard.api.v1.analytics import analytics_bp
from dashboard.api.v1.notifications import notifications_bp
from dashboard.api.v1.presence import presence_bp
from dashboard.api.v1.zones import zones_bp
from dashboard.api.v1.widget_positions import widget_positions_bp


REPO_ROOT = Path(__file__).resolve().parents[5]
VERSION_FILE = REPO_ROOT / "VERSION"


def _runtime_version(default: str = "0.0.0") -> str:
    try:
        version = VERSION_FILE.read_text().strip()
    except OSError:
        return default
    return version or default


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=False,
        APP_NAME="Styx",
        APP_SUITE="PilotSuite",
        APP_VERSION=_runtime_version(),
        WIDGET_POSITIONS_FILE=str(
            Path(__file__).resolve().parent / "dashboard" / "data" / "widget_positions.json"
        ),
    )

    if test_config:
        app.config.update(test_config)

    app.register_blueprint(presence_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(zones_bp)
    app.register_blueprint(widget_positions_bp)

    @app.get("/")
    def index() -> str:
        return "<h1>Styx Dashboard v20.0.0 Core</h1>"

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "pilotsuite-core"}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {
            "name": app.config["APP_NAME"],
            "suite": app.config["APP_SUITE"],
            "version": app.config["APP_VERSION"],
        }

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
