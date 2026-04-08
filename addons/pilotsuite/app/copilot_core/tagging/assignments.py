"""Persistent store for tag assignments."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import threading
from typing import Any, Iterable

__all__ = [
    "ALLOWED_SUBJECT_KINDS",
    "TagAssignment",
    "TagAssignmentStore",
    "TagAssignmentStoreError",
    "TagAssignmentValidationError",
]

ALLOWED_SUBJECT_KINDS: tuple[str, ...] = (
    "entity",
    "device",
    "area",
    "automation",
    "scene",
    "script",
    "helper",
)

_STORE_SCHEMA_VERSION = 1
_ASSIGNMENT_ID_SAFE_RE = re.compile(r"[^a-z0-9_.:#-]+")
_SUBJECT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_META_MAX_KEYS = 20
_META_VALUE_MAX_LEN = 256
_META_KEY_MAX_LEN = 48


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_subject_kind(value: str) -> str:
    candidate = (value or "").strip().lower()
    if candidate not in ALLOWED_SUBJECT_KINDS:
        raise TagAssignmentValidationError(
            f"subject_kind must be one of {', '.join(ALLOWED_SUBJECT_KINDS)}"
        )
    return candidate


def _sanitize_subject_id(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise TagAssignmentValidationError("subject_id is required")
    if not _SUBJECT_ID_RE.match(candidate):
        raise TagAssignmentValidationError(
            "subject_id may only contain letters, digits, '.', '_', '-', ':'"
        )
    return candidate


def _sanitize_tag_id(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise TagAssignmentValidationError("tag_id is required")
    return candidate


def _sanitize_source(value: str | None) -> str:
    candidate = (value or "system").strip().lower()
    if not candidate:
        candidate = "system"
    return candidate


def _sanitize_meta(meta: Any) -> dict[str, str]:
    if not isinstance(meta, dict):
        return {}
    sanitized: dict[str, str] = {}
    for key, value in meta.items():
        if len(sanitized) >= _META_MAX_KEYS:
            break
        key_str = str(key).strip()
        if not key_str:
            continue
        key_str = key_str[:_META_KEY_MAX_LEN]
        if isinstance(value, (dict, list)):
            continue
        value_str = str(value)
        if len(value_str) > _META_VALUE_MAX_LEN:
            value_str = value_str[:_META_VALUE_MAX_LEN]
        sanitized[key_str] = value_str
    return sanitized


def _sanitize_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise TagAssignmentValidationError("confidence must be numeric") from exc
    if num < 0 or num > 1:
        raise TagAssignmentValidationError("confidence must be between 0 and 1")
    return round(num, 4)


def _make_assignment_id(subject_kind: str, subject_id: str, tag_id: str) -> str:
    base = f"{subject_kind}:{subject_id}#{tag_id}".lower()
    return _ASSIGNMENT_ID_SAFE_RE.sub("_", base)


class TagAssignmentValidationError(ValueError):
    """Raised when a supplied assignment payload is invalid."""


class TagAssignmentStoreError(RuntimeError):
    """Raised when the underlying store cannot be loaded or saved."""


@dataclass
class TagAssignment:
    assignment_id: str
    subject_id: str
    subject_kind: str
    tag_id: str
    source: str = "system"
    confidence: float | None = None
    materialized: bool = False
    meta: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TagAssignmentStore:
    """File-backed repository for tag assignments."""

    def __init__(self, path: str | Path, *, max_assignments: int = 2000) -> None:
        self.path = Path(path)
        self.max_assignments = max_assignments
        self._lock = threading.Lock()
        self._assignments: dict[str, TagAssignment] = {}
        self._revision: int = 0
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list(
        self,
        *,
        subject_id: str | None = None,
        subject_kind: str | None = None,
        tag_id: str | None = None,
        materialized: bool | None = None,
        limit: int | None = None,
    ) -> list[TagAssignment]:
        with self._lock:
            items = list(self._assignments.values())
        filtered: list[TagAssignment] = []
        for assignment in items:
            if subject_id and assignment.subject_id != subject_id:
                continue
            if subject_kind and assignment.subject_kind != subject_kind:
                continue
            if tag_id and assignment.tag_id != tag_id:
                continue
            if materialized is not None and assignment.materialized != materialized:
                continue
            filtered.append(assignment)

        filtered.sort(key=lambda a: a.updated_at, reverse=True)
        if limit is not None and limit >= 0:
            filtered = filtered[:limit]
        return filtered

    def upsert(
        self,
        *,
        subject_id: str,
        subject_kind: str,
        tag_id: str,
        source: str = "system",
        confidence: float | None = None,
        meta: dict[str, str] | None = None,
        materialized: bool = False,
    ) -> tuple[TagAssignment, bool]:
        subject_id = _sanitize_subject_id(subject_id)
        subject_kind = _sanitize_subject_kind(subject_kind)
        tag_id = _sanitize_tag_id(tag_id)
        source = _sanitize_source(source)
        confidence = _sanitize_confidence(confidence)
        meta = _sanitize_meta(meta)

        assignment_id = _make_assignment_id(subject_kind, subject_id, tag_id)
        now = _now_iso()

        with self._lock:
            existing = self._assignments.get(assignment_id)
            created = False
            if existing:
                existing.source = source
                existing.confidence = confidence
                existing.materialized = bool(materialized)
                existing.meta = meta
                existing.updated_at = now
                assignment = existing
            else:
                assignment = TagAssignment(
                    assignment_id=assignment_id,
                    subject_id=subject_id,
                    subject_kind=subject_kind,
                    tag_id=tag_id,
                    source=source,
                    confidence=confidence,
                    materialized=bool(materialized),
                    meta=meta,
                )
                assignment.created_at = now
                assignment.updated_at = now
                self._assignments[assignment_id] = assignment
                created = True
            self._revision += 1
            self._prune_locked()
            self._persist_locked()
            return assignment, created

    def remove(self, assignment_ids: Iterable[str]) -> int:
        removed = 0
        with self._lock:
            for assignment_id in assignment_ids:
                if assignment_id in self._assignments:
                    del self._assignments[assignment_id]
                    removed += 1
            if removed:
                self._revision += 1
                self._persist_locked()
        return removed

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._assignments),
                "revision": self._revision,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - catastrophic config
            raise TagAssignmentStoreError(
                f"Could not read tag assignments store: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise TagAssignmentStoreError("Tag assignments store is corrupted")

        assignments = payload.get("assignments", []) or []
        if not isinstance(assignments, list):
            raise TagAssignmentStoreError("Assignments payload must be a list")

        revision = int(payload.get("revision", 0))
        self._revision = max(0, revision)

        loaded: dict[str, TagAssignment] = {}
        for entry in assignments:
            if not isinstance(entry, dict):
                continue
            try:
                assignment = TagAssignment(
                    assignment_id=str(entry.get("assignment_id")),
                    subject_id=str(entry.get("subject_id")),
                    subject_kind=str(entry.get("subject_kind")),
                    tag_id=str(entry.get("tag_id")),
                    source=str(entry.get("source", "system")),
                    confidence=entry.get("confidence"),
                    materialized=bool(entry.get("materialized", False)),
                    meta=entry.get("meta") or {},
                    created_at=str(entry.get("created_at")) if entry.get("created_at") else _now_iso(),
                    updated_at=str(entry.get("updated_at")) if entry.get("updated_at") else _now_iso(),
                )
            except Exception:
                continue
            loaded[assignment.assignment_id] = assignment

        with self._lock:
            self._assignments = loaded

    def _persist_locked(self) -> None:
        payload = {
            "schema_version": _STORE_SCHEMA_VERSION,
            "revision": self._revision,
            "updated_at": _now_iso(),
            "assignments": [
                a.to_dict() for a in sorted(self._assignments.values(), key=lambda a: a.assignment_id)
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)

    def _prune_locked(self) -> None:
        if len(self._assignments) <= self.max_assignments:
            return
        excess = len(self._assignments) - self.max_assignments
        oldest = sorted(
            self._assignments.values(),
            key=lambda a: a.updated_at,
        )[:excess]
        for assignment in oldest:
            self._assignments.pop(assignment.assignment_id, None)

