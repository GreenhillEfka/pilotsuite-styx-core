from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import Flask

from copilot_core.api.v1 import learning_viz as module
from copilot_core.habitus.habitus_storage import FeedbackType, PatternState


@dataclass
class FakePattern:
    id: str
    description: str
    trigger: dict[str, Any]
    action: dict[str, Any]
    confidence: float
    state: PatternState
    acceptances: int
    rejections: int
    zones: list[str]
    modules: list[str]
    last_triggered: str | None = None


@dataclass
class FakeFeedback:
    id: str
    feedback_type: FeedbackType
    timestamp: str
    zone: str | None = None
    module: str | None = None
    comment: str | None = None


class FakeStorage:
    def __init__(self) -> None:
        self.stats = {
            "patterns_total": 8,
            "patterns_by_state": {
                "active": 3,
                "stable": 2,
                "observing": 1,
                "learning": 2,
            },
            "preferences_total": 2,
            "routines_total": 1,
            "feedback_by_type": {
                "accepted": 4,
                "rejected": 1,
            },
            "context_history_total": 7,
        }
        self.patterns = [
            FakePattern(
                id="pattern-living-light",
                description="Morgenlicht im Wohnzimmer",
                trigger={"time": "07:30", "presence": True, "zone": "living"},
                action={"module": "light", "command": "turn_on"},
                confidence=0.912,
                state=PatternState.ACTIVE,
                acceptances=8,
                rejections=1,
                zones=["living"],
                modules=["light"],
                last_triggered="2026-04-05T06:30:00+00:00",
            ),
            FakePattern(
                id="pattern-living-music",
                description="Musik am Abend",
                trigger={"time": "19:00", "zone": "living"},
                action={"module": "music", "command": "play"},
                confidence=0.72,
                state=PatternState.LEARNING,
                acceptances=3,
                rejections=1,
                zones=["living"],
                modules=["music"],
                last_triggered="2026-04-04T18:00:00+00:00",
            ),
            FakePattern(
                id="pattern-office-climate",
                description="Büro temperieren",
                trigger={"time": "08:00", "zone": "office"},
                action={"module": "climate", "command": "set_temperature"},
                confidence=0.81,
                state=PatternState.ACTIVE,
                acceptances=5,
                rejections=0,
                zones=["office"],
                modules=["climate"],
                last_triggered=None,
            ),
        ]
        self.feedbacks = [
            FakeFeedback(
                id="fb_accepted",
                feedback_type=FeedbackType.ACCEPTED,
                timestamp="2026-04-05T06:45:00+00:00",
                zone="living",
                module="light",
                comment="Passt",
            ),
            FakeFeedback(
                id="fb_corrected",
                feedback_type=FeedbackType.CORRECTED,
                timestamp="2026-04-05T06:40:00+00:00",
                zone="office",
                module="climate",
                comment="Bitte wärmer",
            ),
        ]
        self.added_feedback: list[Any] = []
        self.saved_patterns: list[FakePattern] = []

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def get_patterns(
        self,
        zone: str | None = None,
        state: PatternState | None = None,
        min_confidence: float = 0.0,
    ) -> list[FakePattern]:
        patterns = [pattern for pattern in self.patterns if pattern.confidence >= min_confidence]
        if zone is not None:
            patterns = [pattern for pattern in patterns if zone in pattern.zones]
        if state is not None:
            patterns = [pattern for pattern in patterns if pattern.state == state]
        return list(patterns)

    def get_feedback(self, limit: int = 100, **_: Any) -> list[FakeFeedback]:
        return list(self.feedbacks[:limit])

    def add_feedback(self, feedback: Any) -> None:
        self.added_feedback.append(feedback)

    def get_pattern(self, pattern_id: str) -> FakePattern | None:
        for pattern in self.patterns:
            if pattern.id == pattern_id:
                return pattern
        return None

    def save_pattern(self, pattern: FakePattern) -> None:
        self.saved_patterns.append(pattern)


class ExplodingStorage(FakeStorage):
    def __init__(self, target: str, message: str) -> None:
        super().__init__()
        self.target = target
        self.message = message

    def _explode(self, name: str) -> None:
        if self.target == name:
            raise RuntimeError(self.message)

    def get_stats(self) -> dict[str, Any]:
        self._explode("stats")
        return super().get_stats()

    def get_patterns(self, *args: Any, **kwargs: Any) -> list[FakePattern]:
        self._explode("patterns")
        return super().get_patterns(*args, **kwargs)

    def get_feedback(self, *args: Any, **kwargs: Any) -> list[FakeFeedback]:
        self._explode("feedback")
        return super().get_feedback(*args, **kwargs)

    def add_feedback(self, feedback: Any) -> None:
        self._explode("add_feedback")
        super().add_feedback(feedback)


def _build_client(monkeypatch, storage: FakeStorage):
    monkeypatch.setattr(module, "get_habitus_storage", lambda: storage)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(module.learning_viz_bp)
    return app.test_client(), storage


def test_learning_viz_contract_covers_all_routes(monkeypatch) -> None:
    client, storage = _build_client(monkeypatch, FakeStorage())

    response = client.get("/api/v1/learning/overview")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "learning_summary": {
            "patterns": {
                "total": 8,
                "active": 3,
                "stable": 2,
                "observing": 1,
                "learning": 2,
            },
            "preferences": 2,
            "routines": 1,
            "feedback": {
                "total": 5,
                "acceptances": 4,
                "rejections": 1,
                "acceptance_rate": 80.0,
            },
            "context_history": 7,
        },
        "intelligence_score": {
            "total": 55.0,
            "max": 100,
            "breakdown": {
                "patterns_learned": 16,
                "active_automations": 15,
                "user_acceptance": 24.0,
            },
            "level": "Intermediate",
        },
    }

    response = client.get("/api/v1/learning/patterns?zone=living&state=active")
    assert response.status_code == 200
    assert response.get_json() == {
        "total": 1,
        "patterns": [
            {
                "id": "pattern-living-light",
                "description": "Morgenlicht im Wohnzimmer",
                "trigger": "um 07:30 wenn Präsenz erkannt in living",
                "action": "Licht einschalten",
                "confidence": 91.2,
                "state": "active",
                "acceptances": 8,
                "rejections": 1,
                "zones": ["living"],
                "modules": ["light"],
                "last_triggered": "2026-04-05T06:30:00+00:00",
                "human_readable": "Wenn um 07:30 wenn Präsenz erkannt in living, dann Licht einschalten.",
            }
        ],
    }

    response = client.get("/api/v1/learning/progress")
    assert response.status_code == 200
    assert response.get_json() == {
        "by_zone": {
            "living": {"total_patterns": 2, "active_patterns": 1, "learning_progress": 50.0},
            "bath": {"total_patterns": 0, "active_patterns": 0, "learning_progress": 0.0},
            "kitchen": {"total_patterns": 0, "active_patterns": 0, "learning_progress": 0.0},
            "office": {"total_patterns": 1, "active_patterns": 1, "learning_progress": 100.0},
            "bedroom": {"total_patterns": 0, "active_patterns": 0, "learning_progress": 0.0},
            "hallway": {"total_patterns": 0, "active_patterns": 0, "learning_progress": 0.0},
        },
        "by_module": {
            "light": {"total_patterns": 1, "active_patterns": 1, "learning_progress": 100.0},
            "climate": {"total_patterns": 1, "active_patterns": 1, "learning_progress": 100.0},
            "motion": {"total_patterns": 0, "active_patterns": 0, "learning_progress": 0.0},
            "music": {"total_patterns": 1, "active_patterns": 0, "learning_progress": 0.0},
            "energy": {"total_patterns": 0, "active_patterns": 0, "learning_progress": 0.0},
        },
    }

    response = client.get("/api/v1/learning/feedback?limit=1")
    assert response.status_code == 200
    assert response.get_json() == {
        "total": 1,
        "feedbacks": [
            {
                "id": "fb_accepted",
                "type": "accepted",
                "timestamp": "2026-04-05T06:45:00+00:00",
                "zone": "living",
                "module": "light",
                "comment": "Passt",
                "icon": "✅",
                "color": "green",
            }
        ],
    }

    response = client.post(
        "/api/v1/learning/correct",
        json={
            "pattern_id": "pattern-living-light",
            "correction": {"module": "light", "command": "turn_off"},
            "comment": "Bitte abends aus",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": "Korrektur gespeichert. System lernt daraus!",
    }

    assert len(storage.added_feedback) == 1
    feedback = storage.added_feedback[0]
    assert feedback.pattern_id == "pattern-living-light"
    assert feedback.feedback_type == FeedbackType.CORRECTED
    assert feedback.correction == {"module": "light", "command": "turn_off"}
    assert feedback.comment == "Bitte abends aus"

    assert len(storage.saved_patterns) == 1
    assert storage.saved_patterns[0].id == "pattern-living-light"
    assert round(storage.saved_patterns[0].confidence, 3) == 0.73


def test_learning_viz_contract_hardens_validation_and_runtime_errors(monkeypatch) -> None:
    client, _ = _build_client(monkeypatch, FakeStorage())

    response = client.get("/api/v1/learning/patterns?state=invalid")
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "state must be one of: observing, learning, stable, active, disabled"
    }

    response = client.get("/api/v1/learning/feedback?limit=0")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be a positive integer"}

    response = client.get("/api/v1/learning/feedback?limit=abc")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be a positive integer"}

    response = client.post("/api/v1/learning/correct")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body required"}

    response = client.post(
        "/api/v1/learning/correct",
        data="{",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid JSON body"}

    response = client.post("/api/v1/learning/correct", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/learning/correct", json={"pattern_id": 7})
    assert response.status_code == 400
    assert response.get_json() == {"error": "pattern_id must be a string"}

    response = client.post("/api/v1/learning/correct", json={"pattern_id": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"error": "pattern_id must be a non-empty string"}

    response = client.post("/api/v1/learning/correct", json={"correction": "turn it off"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "correction must be an object"}

    response = client.post("/api/v1/learning/correct", json={"comment": 123})
    assert response.status_code == 400
    assert response.get_json() == {"error": "comment must be a string"}

    client, _ = _build_client(monkeypatch, ExplodingStorage("stats", "stats exploded"))
    response = client.get("/api/v1/learning/overview")
    assert response.status_code == 500
    assert response.get_json() == {"error": "stats exploded"}

    client, _ = _build_client(monkeypatch, ExplodingStorage("patterns", "patterns exploded"))
    response = client.get("/api/v1/learning/patterns")
    assert response.status_code == 500
    assert response.get_json() == {"error": "patterns exploded"}

    response = client.get("/api/v1/learning/progress")
    assert response.status_code == 500
    assert response.get_json() == {"error": "patterns exploded"}

    client, _ = _build_client(monkeypatch, ExplodingStorage("feedback", "feedback exploded"))
    response = client.get("/api/v1/learning/feedback")
    assert response.status_code == 500
    assert response.get_json() == {"error": "feedback exploded"}

    client, _ = _build_client(monkeypatch, ExplodingStorage("add_feedback", "correction exploded"))
    response = client.post(
        "/api/v1/learning/correct",
        json={"pattern_id": "pattern-living-light", "correction": {"module": "light"}},
    )
    assert response.status_code == 500
    assert response.get_json() == {"error": "correction exploded"}
