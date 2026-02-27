import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


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


def _exponential_decay_weight(age_seconds: float, half_life_seconds: float) -> float:
    """Exponential decay: w(t) = exp(-ln(2) * t / half_life).

    At t=0: weight=1.0
    At t=half_life: weight=0.5
    At t=2*half_life: weight=0.25
    """
    if age_seconds <= 0:
        return 1.0
    if half_life_seconds <= 0:
        return 0.0
    lam = math.log(2) / half_life_seconds
    return math.exp(-lam * age_seconds)


class MoodScorer:
    """Mood scoring from conversation and HA events (v2.0).

    Improvements over v1.0:
    - Temporal decay: recent events weighted more heavily via exponential decay
    - Tanh normalization: smooth, bounded output without hard clipping
    - Confidence estimation: based on event density and signal strength
    """

    def __init__(
        self,
        *,
        window_seconds: int = 3600,
        event_weights: dict[str, float] | None = None,
        neutral_threshold: float = 0.15,
        half_life_seconds: float = 900.0,
    ):
        self.window_seconds = window_seconds
        self.weights = {**_EVENT_WEIGHTS, **(event_weights or {})}
        self.neutral_threshold = max(0.01, min(0.5, neutral_threshold))
        self.half_life_seconds = half_life_seconds

    def score_from_events(self, events: list[dict[str, Any]]) -> MoodScore:
        """Score mood using temporally-weighted sentiment analysis.

        Each event's contribution is weighted by:
        1. Its sentiment weight (from _EVENT_WEIGHTS)
        2. Its temporal decay (exponential, based on age)

        Final score uses tanh normalization for smooth [-1, +1] output
        instead of hard clipping.
        """
        if not events:
            return MoodScore(
                ts=_now_iso(),
                window_seconds=self.window_seconds,
                score=0.0,
                label="neutral",
                signals={"pos": 0, "neg": 0, "n_events": 0, "weighted": True},
            )

        now = _now_ts()
        weighted_sum = 0.0
        decay_weight_total = 0.0
        pos_count = 0
        neg_count = 0

        for event in events:
            event_type = str(event.get("type", ""))
            sentiment_w = self.weights.get(event_type, 0.0)

            if sentiment_w > 0:
                pos_count += 1
            elif sentiment_w < 0:
                neg_count += 1

            # Temporal decay based on event timestamp
            event_ts = event.get("timestamp")
            if event_ts:
                if isinstance(event_ts, str):
                    try:
                        event_dt = datetime.fromisoformat(event_ts.replace("Z", "+00:00"))
                        age_seconds = max(0.0, now - event_dt.timestamp())
                    except (ValueError, TypeError):
                        age_seconds = 0.0
                elif isinstance(event_ts, (int, float)):
                    age_seconds = max(0.0, now - event_ts)
                else:
                    age_seconds = 0.0
            else:
                age_seconds = 0.0

            decay_w = _exponential_decay_weight(age_seconds, self.half_life_seconds)

            # Combined weight: sentiment * temporal decay
            weighted_sum += sentiment_w * decay_w
            decay_weight_total += abs(sentiment_w) * decay_w if sentiment_w != 0.0 else 0.0

        # Tanh normalization: smooth, bounded [-1, +1] without hard clipping
        # tanh(x) naturally compresses extreme values
        if decay_weight_total > 0:
            raw = weighted_sum / decay_weight_total
        else:
            raw = 0.0

        # Scale factor controls sensitivity (higher = more responsive to mild signals)
        scale = 2.0
        score = math.tanh(raw * scale)

        # Confidence: based on total decayed signal strength
        # More events + stronger signals + more recent = higher confidence
        # Sigmoid: maps (0, inf) → (0, 1) with midpoint at ~3 weighted events
        confidence = 1.0 / (1.0 + math.exp(-0.5 * (decay_weight_total - 3.0)))

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
            score=round(score, 3),
            label=label,
            signals={
                "pos": pos_count,
                "neg": neg_count,
                "n_events": len(events),
                "weighted": True,
                "decay_weight_total": round(decay_weight_total, 3),
                "confidence": round(confidence, 3),
                "half_life_seconds": self.half_life_seconds,
            },
        )
