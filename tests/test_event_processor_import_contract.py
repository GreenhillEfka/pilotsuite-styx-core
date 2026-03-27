"""Regression coverage for ingest/event_processor import wiring."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


def test_event_processor_imports_feed_brain_from_core_package() -> None:
    module = import_module("copilot_core.ingest.event_processor")

    assert module.feed_brain.__module__ == "copilot_core.core.brain_read_model"
    assert callable(module.feed_brain)
