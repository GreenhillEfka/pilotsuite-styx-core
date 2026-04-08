"""Regression tests for the TagAssignmentStore."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot_core.tagging.assignments import (
    ALLOWED_SUBJECT_KINDS,
    TagAssignmentStore,
    TagAssignmentValidationError,
)


def _make_store() -> tuple[TagAssignmentStore, Path]:
    temp_dir = tempfile.TemporaryDirectory()
    path = Path(temp_dir.name) / "assignments.json"
    store = TagAssignmentStore(path, max_assignments=5)
    # Attach temporary directory to store for GC (simple attribute).
    store._tmp = temp_dir  # type: ignore[attr-defined]
    return store, path


def test_upsert_roundtrip():
    store, path = _make_store()
    assignment, created = store.upsert(
        subject_id="light.kitchen",
        subject_kind="entity",
        tag_id="aicp.kind.light",
        source="core",
        confidence=0.8,
        meta={"reason": "bootstrap"},
        materialized=True,
    )
    assert created is True
    assert assignment.assignment_id
    assert assignment.materialized is True
    assert assignment.meta["reason"] == "bootstrap"

    # Persisted file should exist and contain assignments
    data = path.read_text(encoding="utf-8")
    assert "light.kitchen" in data

    # Reload store from disk and ensure assignment is kept
    store_reloaded = TagAssignmentStore(path)
    items = store_reloaded.list()
    assert len(items) == 1
    assert items[0].assignment_id == assignment.assignment_id

    # Update same assignment toggling materialized flag
    updated, created_second = store_reloaded.upsert(
        subject_id="light.kitchen",
        subject_kind="entity",
        tag_id="aicp.kind.light",
        materialized=False,
    )
    assert created_second is False
    assert updated.materialized is False


def test_validation_rules():
    store, _ = _make_store()
    try:
        store.upsert(subject_id="", subject_kind="entity", tag_id="aicp.kind.light")
        raise AssertionError("expected validation error for empty subject_id")
    except TagAssignmentValidationError:
        pass

    try:
        store.upsert(subject_id="bad id", subject_kind="entity", tag_id="aicp.kind.light")
        raise AssertionError("expected validation error for subject_id pattern")
    except TagAssignmentValidationError:
        pass

    try:
        store.upsert(subject_id="light.kitchen", subject_kind="invalid", tag_id="aicp.kind.light")
        raise AssertionError("expected validation error for subject_kind")
    except TagAssignmentValidationError:
        pass

    allowed = set(ALLOWED_SUBJECT_KINDS)
    assert "entity" in allowed


def test_pruning_keeps_newest():
    store, _ = _make_store()
    for idx in range(10):
        store.upsert(
            subject_id=f"light.{idx}",
            subject_kind="entity",
            tag_id="aicp.kind.light",
        )
    summary = store.summary()
    assert summary["count"] == store.max_assignments


test_upsert_roundtrip()
test_validation_rules()
test_pruning_keeps_newest()
