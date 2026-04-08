import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        self._order: list[str] = []

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
        except Exception:
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

        # evict if needed
        while len(self._order) > self.max_items:
            victim = self._order.pop(0)
            self._items.pop(victim, None)

        self._persist()
        return cand

    def get(self, cid: str) -> Optional[dict[str, Any]]:
        return self._items.get(cid)

    def delete(self, cid: str) -> bool:
        if cid not in self._items:
            return False
        self._items.pop(cid, None)
        self._order = [x for x in self._order if x != cid]
        self._persist()
        return True

    def list(self, *, limit: int = 50, kind: Optional[str] = None) -> list[dict[str, Any]]:
        ids = self._order
        if kind:
            ids = [cid for cid in ids if str(self._items.get(cid, {}).get("kind", "")) == kind]
        limit = max(1, min(int(limit), self.max_items))
        return [self._items[cid] for cid in ids[-limit:] if cid in self._items]
