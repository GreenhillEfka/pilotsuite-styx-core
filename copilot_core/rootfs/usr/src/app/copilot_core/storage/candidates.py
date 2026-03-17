import json
import logging
import math
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Utility-based candidate ranking
# ---------------------------------------------------------------------------

def rank_score(candidate: dict[str, Any], *, all_candidates: list[dict[str, Any]] | None = None) -> float:
    """Calculate a utility-based ranking score for a candidate.

    Score formula:
        score = (confidence * 0.4)
              + (support_normalized * 0.2)
              + (lift_normalized * 0.15)
              + (recency * 0.15)
              + (user_affinity * 0.1)

    All component values are clamped to [0, 1].  Missing fields gracefully
    default so the function never raises on incomplete data.
    """
    attrs = candidate.get("attributes") or {}
    evidence = attrs.get("evidence") or attrs  # evidence may be nested or flat

    # --- confidence (from pattern) ---
    confidence = _safe_float(evidence, "confidence", _safe_float(attrs, "confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    # --- support_normalized: log(support_count) / log(max_support) ---
    support_count = _safe_float(evidence, "support_count",
                                _safe_float(evidence, "nAB",
                                            _safe_float(evidence, "weight", 0.0)))
    max_support = support_count  # default: self-normalise to 1.0
    if all_candidates:
        max_support = _max_support_across(all_candidates)
    max_support = max(max_support, 1.0)
    support_normalized = math.log(max(1.0, support_count)) / math.log(max(2.0, max_support))
    support_normalized = max(0.0, min(1.0, support_normalized))

    # --- lift_normalized: min(lift, 3.0) / 3.0 ---
    lift = _safe_float(evidence, "lift", 1.0)
    lift_normalized = min(lift, 3.0) / 3.0
    lift_normalized = max(0.0, min(1.0, lift_normalized))

    # --- recency: 1.0 - (age_days / 30.0), clamped to [0, 1] ---
    created_str = candidate.get("created", "")
    age_days = _age_in_days(created_str)
    recency = max(0.0, min(1.0, 1.0 - (age_days / 30.0)))

    # --- user_affinity: acceptance rate for domain (default 0.5) ---
    user_affinity = _safe_float(attrs, "user_affinity",
                                _safe_float(attrs, "acceptance_rate", 0.5))
    user_affinity = max(0.0, min(1.0, user_affinity))

    return round(
        (confidence * 0.4)
        + (support_normalized * 0.2)
        + (lift_normalized * 0.15)
        + (recency * 0.15)
        + (user_affinity * 0.1),
        6,
    )


def generate_explanation(candidate: dict[str, Any]) -> str:
    """Generate a natural-language explanation for a candidate (German).

    Returns a human-readable sentence such as:
        "Du schaltest 15x morgens zwischen 7-9 Uhr das Kuechenlicht ein,
         nachdem du aufgestanden bist (87% Vertrauen)"

    Falls back to a generic description when data is sparse.
    """
    attrs = candidate.get("attributes") or {}
    evidence = attrs.get("evidence") or attrs
    label = candidate.get("label") or ""

    confidence = _safe_float(evidence, "confidence", _safe_float(attrs, "confidence", 0.0))
    conf_pct = int(round(confidence * 100))

    support_count = int(_safe_float(evidence, "support_count",
                                    _safe_float(evidence, "nAB",
                                                _safe_float(evidence, "weight", 0))))

    # Try to extract entity names from various formats
    from_id = attrs.get("from", evidence.get("from", ""))
    to_id = attrs.get("to", evidence.get("to", ""))

    # Try time-pattern context
    time_pattern = attrs.get("time_pattern", evidence.get("time_pattern", ""))
    context_str = attrs.get("context", evidence.get("context", ""))

    # Build entity display names (strip ha.entity: prefix, replace dots/underscores)
    from_name = _entity_display_name(from_id)
    to_name = _entity_display_name(to_id)

    # Construct explanation parts
    parts: list[str] = []

    if from_name and to_name:
        if support_count > 0:
            parts.append(f"{to_name} wird {support_count}x aktiviert, nachdem {from_name} ausgeloest wurde")
        else:
            parts.append(f"{to_name} folgt regelmaessig auf {from_name}")
    elif label:
        if support_count > 0:
            parts.append(f"{label} wurde {support_count}x beobachtet")
        else:
            parts.append(label)
    else:
        parts.append("Muster im Nutzungsverhalten erkannt")

    if time_pattern:
        parts.append(f"({time_pattern})")
    elif context_str:
        parts.append(f"({context_str})")

    if conf_pct > 0:
        parts.append(f"({conf_pct}% Vertrauen)")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(d: dict, key: str, default: float = 0.0) -> float:
    """Extract a float from dict, returning *default* on any failure."""
    try:
        val = d.get(key)
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _age_in_days(iso_str: str) -> float:
    """Return age in days from an ISO-8601 timestamp string.  0.0 on failure."""
    if not iso_str:
        return 0.0
    try:
        created_dt = datetime.fromisoformat(iso_str)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - created_dt
        return max(0.0, delta.total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return 0.0


def _max_support_across(candidates: list[dict[str, Any]]) -> float:
    """Find max support count across all candidates for normalisation."""
    best = 1.0
    for c in candidates:
        attrs = c.get("attributes") or {}
        ev = attrs.get("evidence") or attrs
        val = _safe_float(ev, "support_count",
                          _safe_float(ev, "nAB",
                                      _safe_float(ev, "weight", 0.0)))
        if val > best:
            best = val
    return best


def _entity_display_name(entity_id: str) -> str:
    """Convert an entity_id into a readable German display name.

    Examples:
        "ha.entity:light.kueche" -> "Kuechenlicht"
        "light.kitchen"          -> "Kitchen"
        ""                       -> ""
    """
    if not entity_id:
        return ""
    # Strip common prefixes
    name = entity_id
    if name.startswith("ha.entity:"):
        name = name[len("ha.entity:"):]
    # Remove domain prefix for display (keep for context)
    parts = name.split(".", 1)
    domain = parts[0] if len(parts) > 1 else ""
    entity_name = parts[1] if len(parts) > 1 else parts[0]
    # Replace underscores with spaces, capitalise
    display = entity_name.replace("_", " ").strip().title()
    if domain:
        display = f"{display} ({domain})"
    return display


@dataclass
class Candidate:
    """A candidate is an intermediate hypothesis.

    Examples:
    - inferred task/reminder request
    - intent classification result
    - entity resolution candidate
    - room/user context guess
    """

    id: str
    kind: str
    label: str
    score: float = 0.0
    created: str = ""
    updated: str = ""
    source: str = ""
    attributes: dict[str, Any] | None = None

    @staticmethod
    def from_payload(payload: dict[str, Any]) -> "Candidate":
        cid = str(payload.get("id") or payload.get("candidate_id") or "")
        if not cid:
            cid = f"cand_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        now = _now_iso()
        created = str(payload.get("created") or now)
        return Candidate(
            id=cid,
            kind=str(payload.get("kind") or payload.get("type") or "unknown"),
            label=str(payload.get("label") or payload.get("name") or ""),
            score=float(payload.get("score") or 0.0),
            created=created,
            updated=str(payload.get("updated") or now),
            source=str(payload.get("source") or ""),
            attributes=(payload.get("attributes") if isinstance(payload.get("attributes"), dict) else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "score": self.score,
            "created": self.created,
            "updated": self.updated,
            "source": self.source,
            "attributes": self.attributes or {},
        }


class CandidateStore:
    """Tiny candidate store.

    Safe defaults:
    - in-memory only unless enabled.
    - capped size; evicts oldest by insertion order.
    """

    def __init__(self, *, max_items: int = 500, persist: bool = False, json_path: str = "/data/candidates.json"):
        self.max_items = max(1, max_items)
        self.persist = bool(persist)
        self.json_path = json_path
        self._items: dict[str, dict[str, Any]] = {}
        self._order: deque[str] = deque()

        if self.persist:
            self._load()

    def _load(self) -> None:
        try:
            with open(self.json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
            items = data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict) and it.get("id"):
                        cid = str(it["id"])
                        self._items[cid] = it
                        self._order.append(cid)
        except (IOError, json.JSONDecodeError, KeyError, TypeError):
            return

    def _persist(self) -> None:
        if not self.persist:
            return
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        tmp = self.json_path + ".tmp"
        payload = {"updated": _now_iso(), "items": [self._items[c] for c in self._order if c in self._items]}
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, self.json_path)

    def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        cand = Candidate.from_payload(payload).to_dict()
        cid = cand["id"]

        if cid in self._items:
            # keep original created if present
            cand["created"] = self._items[cid].get("created", cand.get("created"))
            self._items[cid] = cand
        else:
            self._items[cid] = cand
            self._order.append(cid)

        # evict if needed (O(1) with deque.popleft)
        while len(self._order) > self.max_items:
            victim = self._order.popleft()
            self._items.pop(victim, None)

        self._persist()
        return cand

    def get(self, cid: str) -> Optional[dict[str, Any]]:
        return self._items.get(cid)

    def delete(self, cid: str) -> bool:
        if cid not in self._items:
            return False
        self._items.pop(cid, None)
        self._order = deque(x for x in self._order if x != cid)
        self._persist()
        return True

    def list(self, *, limit: int = 50, kind: Optional[str] = None) -> list[dict[str, Any]]:
        ids = list(self._order)
        if kind:
            ids = [cid for cid in ids if str(self._items.get(cid, {}).get("kind", "")) == kind]
        limit = max(1, min(int(limit), self.max_items))
        return [self._items[cid] for cid in ids[-limit:] if cid in self._items]

    def list_ranked(self, *, limit: int = 50, kind: Optional[str] = None,
                    with_explanation: bool = True) -> list[dict[str, Any]]:
        """Return candidates sorted by utility-based ranking score.

        Each returned dict gets two extra keys:
        - ``rank_score``: float in [0, 1]
        - ``explanation``: natural-language German string (if *with_explanation*)
        """
        # Gather base list (use a high internal limit so ranking sees all)
        base = self.list(limit=self.max_items, kind=kind)
        if not base:
            return []

        # Enrich each candidate with score and explanation
        enriched: list[dict[str, Any]] = []
        for item in base:
            copy = dict(item)
            try:
                copy["rank_score"] = rank_score(copy, all_candidates=base)
            except Exception:
                copy["rank_score"] = 0.0
            if with_explanation:
                try:
                    copy["explanation"] = generate_explanation(copy)
                except Exception:
                    copy["explanation"] = ""
            enriched.append(copy)

        # Sort descending by rank_score
        enriched.sort(key=lambda c: c.get("rank_score", 0.0), reverse=True)

        # Apply limit
        limit = max(1, min(int(limit), self.max_items))
        return enriched[:limit]
