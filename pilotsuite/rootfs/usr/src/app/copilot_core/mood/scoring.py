from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MoodScore:
    """Output for mood scoring.

    Privacy-first: no PII inference, no long retention.
    """

    ts: str
    window_seconds: int
    score: float  # -1..+1
    label: str
    signals: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "window_seconds": self.window_seconds,
            "score": self.score,
            "label": self.label,
            "signals": self.signals,
        }


# Weighted event type mappings: type -> sentiment weight (-1.0 .. +1.0)
_EVENT_WEIGHTS: dict[str, float] = {
    # Positive signals
    "compliment": 0.8,
    "positive": 0.6,
    "thanks": 0.5,
    "greeting": 0.3,
    "music_started": 0.4,
    "scene_activated": 0.3,
    "automation_success": 0.2,
    "presence_home": 0.2,
    # Negative signals
    "complaint": -0.8,
    "negative": -0.6,
    "frustration": -0.9,
    "error": -0.4,
    "automation_failure": -0.5,
    "device_unavailable": -0.3,
    "timeout": -0.3,
}


class MoodScorer:
    """Mood scoring from conversation and HA events.

    Uses weighted event type mapping with configurable weights and
    normalized scoring.
    """

    def __init__(
        self,
        *,
        window_seconds: int = 3600,
        event_weights: dict[str, float] | None = None,
        neutral_threshold: float = 0.15,
    ):
        self.window_seconds = window_seconds
        self.weights = {**_EVENT_WEIGHTS, **(event_weights or {})}
        self.neutral_threshold = max(0.01, min(0.5, neutral_threshold))

    def score_from_events(self, events: list[dict[str, Any]]) -> MoodScore:
        """Score mood from a list of events using weighted sentiment analysis."""
        if not events:
            return MoodScore(
                ts=_now_iso(),
                window_seconds=self.window_seconds,
                score=0.0,
                label="neutral",
                signals={"pos": 0, "neg": 0, "n_events": 0, "weighted": True},
            )

        weighted_sum = 0.0
        weight_total = 0.0
        pos_count = 0
        neg_count = 0

        for event in events:
            event_type = str(event.get("type", ""))
            w = self.weights.get(event_type, 0.0)

            if w > 0:
                pos_count += 1
            elif w < 0:
                neg_count += 1

            weighted_sum += w
            weight_total += abs(w) if w != 0.0 else 0.0

        # Normalize to -1..+1 range
        if weight_total > 0:
            raw = weighted_sum / weight_total
        else:
            raw = 0.0

        score = max(-1.0, min(1.0, float(raw)))

        # Label with configurable threshold
        if score > self.neutral_threshold:
            label = "positive"
        elif score < -self.neutral_threshold:
            label = "negative"
        else:
            label = "neutral"

        return MoodScore(
            ts=_now_iso(),
            window_seconds=self.window_seconds,
            score=score,
            label=label,
            signals={
                "pos": pos_count,
                "neg": neg_count,
                "n_events": len(events),
                "weighted": True,
                "weight_total": round(weight_total, 3),
            },
        )
